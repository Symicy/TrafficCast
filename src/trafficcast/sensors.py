"""Un proces independent per direcție; un singur adaptor citește SUMO."""

import multiprocessing as mp
from queue import Empty
import signal
import time

from .messages import DIRECTIONS, Measurement
from .runtime import Shutdown
from .sources import sumo_frames
from .tracing import trace
from .transport import close, connect, publish


def sensor_worker(direction, incoming, acknowledgements, host, port):
    # Părintele gestionează Ctrl+C și închide coordonat procesele copil.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.SIG_IGN)
    client = None
    try:
        client = connect(host, port, f"sensor-{direction}")
        acknowledgements.put((direction, "ready"))
        while (measurement := incoming.get()) is not None:
            trace("MQTT_PUBLISH", measurement)
            publish(client, measurement)
            trace("MQTT_PUBACK", measurement)
            acknowledgements.put((direction, measurement.sequence))
    except Exception as exc:
        print(f"SENZOR_EȘUAT {direction}: {exc}", flush=True)
        raise
    finally:
        if client:
            close(client)


def wait_for(acknowledgements, workers, expected):
    pending = set(workers)
    deadline = time.monotonic() + 15
    while pending:
        for direction in list(pending):
            if not workers[direction].is_alive():
                if expected == "ready":
                    raise RuntimeError(f"Senzorul {direction} nu a pornit")
                print(f"SENZOR_OPRIT {direction}; celelalte direcții continuă", flush=True)
                pending.remove(direction)
        if not pending:
            break
        if time.monotonic() > deadline:
            raise TimeoutError(f"Lipsește confirmarea {expected} de la {sorted(pending)}")
        try:
            direction, sequence = acknowledgements.get(timeout=0.1)
            if sequence == expected:
                pending.discard(direction)
        except Empty:
            pass


def run_sensors(args):
    with Shutdown() as stop:
        _run_sensors(args, stop)


def _run_sensors(args, stop):
    # Validează run_id înainte de a porni procesele sau simularea.
    Measurement(args.run_id, "E2_N", "N", 1, 0, "sumo", 0, None, 0, 0, 0, 0)
    frames = sumo_frames(args.scenario, args.steps, args.gui, args.sumo_backend, args.continuous,
                         seed=args.seed, profile=args.profile, demand_duration=args.demand_duration)
    context = mp.get_context("spawn")
    acknowledgements = context.Queue()
    queues = {direction: context.Queue(maxsize=2) for direction in DIRECTIONS}
    workers = {}
    try:
        for direction in DIRECTIONS:
            worker = context.Process(
                target=sensor_worker, name=f"sensor-{direction}",
                args=(direction, queues[direction], acknowledgements, args.host, args.port),
            )
            worker.start()
            workers[direction] = worker
            print(f"SENZOR_PORNIT {direction} pid={worker.pid}", flush=True)
        wait_for(acknowledgements, workers, "ready")
        count = 0
        for sequence, frame in enumerate(frames, 1):
            if stop.is_set():
                break
            active = {d: w for d, w in workers.items() if w.is_alive()}
            if not active:
                raise RuntimeError("Toate procesele senzor s-au oprit")
            for direction in DIRECTIONS:
                reading = frame[direction]
                message = Measurement(
                    run_id=args.run_id, sensor_id=f"E2_{direction}", sequence=sequence,
                    source="sumo", **reading,
                )
                trace("SUMO_READ", message)
                if direction in active:
                    queues[direction].put(message, timeout=2)
                    count += 1
            wait_for(acknowledgements, active, sequence)
            if stop.wait(args.pace):
                break
        print(f"FLUX_TERMINAT run={args.run_id} mesaje_trimise={count}", flush=True)
    finally:
        try:
            frames.close()
        except Exception as exc:
            print(f"Închiderea sursei: {exc}", flush=True)
        for direction, worker in workers.items():
            if worker.is_alive():
                try:
                    queues[direction].put(None, timeout=1)
                except Exception:
                    worker.terminate()
        for worker in workers.values():
            worker.join(timeout=3)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=3)
        for queue in [*queues.values(), acknowledgements]:
            queue.cancel_join_thread()
            queue.close()
