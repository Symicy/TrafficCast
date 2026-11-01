"""Citirea și agregarea detectoarelor SUMO prin unicul client TraCI."""

import itertools
import math
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from .messages import DIRECTIONS
from .runtime import sumo_executable


def sumo_command(scenario, gui, backend):
    scenario = Path(scenario).resolve()
    if not scenario.is_file():
        raise FileNotFoundError(scenario)
    command = sumo_executable("sumo-gui" if gui else "sumo", scenario.parent, backend)
    return command + ["-c", str(scenario), "--no-step-log", "true"] + (
        ["--start", "--quit-on-end"] if gui else [])


def run_scenario(scenario, action, backend):
    scenario = Path(scenario).resolve()
    if not scenario.is_file():
        raise FileNotFoundError(scenario)
    (scenario.parent / "results").mkdir(exist_ok=True)
    if action == "rebuild":
        command = sumo_executable("netconvert", scenario.parent, backend)
        command += ["-c", str(scenario.parent / "intersection.netccfg")]
    else:
        command = sumo_command(scenario, action == "gui", backend)
    result = subprocess.run(command, check=False)
    if result.returncode:
        raise RuntimeError(f"SUMO/{action} s-a închis cu codul {result.returncode}")


def detector_groups(connection):
    """Un detector pe fiecare bandă, acceptând și numele scenariului inițial."""
    groups = {}
    for direction in DIRECTIONS:
        pairs = []
        for domain, prefix, edge in ((connection.lanearea, f"E2_{direction}", f"{direction}_in"),
                                      (connection.inductionloop, f"E1_{direction}_out", f"{direction}_out")):
            ids = [item for item in domain.getIDList()
                   if item == prefix or (item.startswith(prefix + "_") and item[len(prefix) + 1:].isdigit())]
            expected = {f"{edge}_{i}" for i in range(connection.edge.getLaneNumber(edge))}
            lanes = [domain.getLaneID(item) for item in ids]
            if set(lanes) != expected or len(lanes) != len(expected):
                raise ValueError(f"Detectoare lipsă, suprapuse sau incorecte pentru {edge}: {ids}")
            pairs.append(sorted(ids))
        groups[direction] = pairs
    return groups


def read_direction(connection, direction, detectors, phase):
    entries, exits = detectors
    readings = [(connection.lanearea.getLastStepVehicleNumber(item),
                 connection.lanearea.getLastStepMeanSpeed(item)) for item in entries]
    available = [(number, speed) for number, speed in readings if number > 0 and speed >= 0]
    weight = sum(number for number, _ in available)
    return dict(
        sim_time_s=connection.simulation.getTime(), direction=direction,
        vehicle_count=sum(number for number, _ in readings),
        mean_speed_m_s=sum(number * speed for number, speed in available) / weight if weight else None,
        occupancy_pct=sum(connection.lanearea.getLastStepOccupancy(item) for item in entries) / len(entries),
        jam_length_m=max(connection.lanearea.getJamLengthMeters(item) for item in entries),
        exit_vehicle_count=sum(connection.inductionloop.getLastStepVehicleNumber(item) for item in exits),
        tls_phase=phase,
    )


class ContinuousDemand:
    """Continuă fluxurile periodice livrate, după finalul lor, fără resetare."""

    def __init__(self, scenario):
        config = ET.parse(scenario).getroot()
        route_files = config.find("input/route-files").get("value").split(",")
        self.flows = []
        for filename in route_files:
            for flow in ET.parse(Path(scenario).parent / filename.strip()).getroot().findall("flow"):
                attrs = flow.attrib
                if not all(key in attrs for key in ("id", "route", "period", "end")):
                    raise ValueError("Modul continuu cere fluxuri cu id, route, period numeric și end explicit")
                period = float(attrs["period"])
                begin, end = float(attrs.get("begin", 0)), float(attrs["end"])
                if not math.isfinite(period) or period <= 0 or not math.isfinite(end) or end < begin:
                    raise ValueError("Perioadă sau interval invalid pentru fluxul continuu")
                unsupported = set(attrs) - {"id", "route", "period", "begin", "end", "type", "departLane", "departSpeed"}
                if unsupported:
                    raise ValueError(f"Atribute nesuportate în modul continuu: {sorted(unsupported)}")
                self.flows.append(dict(attrs=attrs, period=period,
                                       next=begin + math.ceil((end - begin) / period) * period,
                                       sequence=0))
        if not self.flows:
            raise ValueError("Scenariul nu conține fluxuri periodice pentru modul continuu")

    def extend(self, connection):
        horizon = connection.simulation.getTime() + connection.simulation.getDeltaT()
        for flow in self.flows:
            attrs = flow["attrs"]
            while flow["next"] < horizon:
                connection.vehicle.add(
                    f"{attrs['id']}.continuous.{flow['sequence']}", attrs["route"],
                    typeID=attrs.get("type", "DEFAULT_VEHTYPE"), depart=str(flow["next"]),
                    departLane=attrs.get("departLane", "first"), departSpeed=attrs.get("departSpeed", "0"),
                )
                flow["sequence"] += 1
                flow["next"] += flow["period"]


def sumo_frames(scenario, steps, gui, backend, continuous=False,
                seed=None, profile="baseline", demand_duration=1800, route_file=None):
    import traci

    scenario = Path(scenario).resolve()
    demand = ContinuousDemand(scenario) if continuous and profile == "baseline" else None
    (scenario.parent / "results").mkdir(exist_ok=True)
    command = sumo_command(scenario, gui, backend)
    if seed is not None:
        command += ["--seed", str(seed)]
    if route_file is not None:
        command += ["--route-files", str(Path(route_file).resolve())]
    if profile != "baseline":
        from .demand import ProfileDemand
        demand = ProfileDemand(scenario, profile, seed if seed is not None else 42,
                               demand_duration, continuous)
        command += ["--route-files", str(demand.static_file)]
    connection = None
    try:
        traci.start(command, label="trafficcast")
        connection = traci.getConnection("trafficcast")
        groups = detector_groups(connection)
        from .telemetry import Telemetry
        telemetry = Telemetry(connection, groups)
        for _ in itertools.count() if continuous else range(steps):
            if demand:
                demand.extend(connection)
            connection.simulationStep()
            frame = telemetry.frame()
            yield frame
    finally:
        try:
            if connection is not None:
                connection.close()
        finally:
            if profile != "baseline":
                demand.close()
