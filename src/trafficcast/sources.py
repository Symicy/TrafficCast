"""Citirea în timp real a detectoarelor din SUMO prin TraCI."""

from pathlib import Path
import shutil

from .messages import DIRECTIONS


def sumo_command(scenario, gui, backend):
    binary = "sumo-gui" if gui else "sumo"
    scenario = Path(scenario).resolve()
    if not scenario.is_file():
        raise FileNotFoundError(scenario)
    if backend == "native" or (backend == "auto" and shutil.which(binary)):
        if not shutil.which(binary):
            raise RuntimeError(f"Executabilul {binary} nu este în PATH")
        command = [binary]
    else:
        if not shutil.which("flatpak"):
            raise RuntimeError("Nu am găsit SUMO nativ sau Flatpak")
        command = ["flatpak", "run", f"--filesystem={scenario.parent}",
                   "--share=network", f"--command={binary}", "org.eclipse.sumo"]
    return command + ["-c", str(scenario), "--no-step-log", "true"] + (["--start"] if gui else [])


def sumo_frames(scenario, steps, gui, backend):
    import traci

    scenario = Path(scenario).resolve()
    (scenario.parent / "results").mkdir(exist_ok=True)
    traci.start(sumo_command(scenario, gui, backend), label="trafficcast")
    connection = traci.getConnection("trafficcast")
    try:
        expected = {f"E2_{d}" for d in DIRECTIONS}
        if not expected.issubset(connection.lanearea.getIDList()):
            raise ValueError("Scenariul nu conține toate detectoarele E2 așteptate")
        for _ in range(steps):
            connection.simulationStep()
            phase = connection.trafficlight.getPhase("J0")
            frame = {}
            for direction in DIRECTIONS:
                detector = f"E2_{direction}"
                speed = connection.lanearea.getLastStepMeanSpeed(detector)
                frame[direction] = dict(
                    sim_time_s=connection.simulation.getTime(), direction=direction,
                    vehicle_count=connection.lanearea.getLastStepVehicleNumber(detector),
                    mean_speed_m_s=speed if speed >= 0 else None,
                    occupancy_pct=connection.lanearea.getLastStepOccupancy(detector),
                    jam_length_m=connection.lanearea.getJamLengthMeters(detector),
                    exit_vehicle_count=connection.inductionloop.getLastStepVehicleNumber(f"E1_{direction}_out"),
                    tls_phase=phase,
                )
            yield frame
    finally:
        connection.close()
