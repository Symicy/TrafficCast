"""Cerere reproductibilă: intrări explicite pentru experimente și profil continuu."""

from copy import deepcopy
from pathlib import Path
import random
import tempfile
import xml.etree.ElementTree as ET

PROFILES = ("baseline", "balanced", "switching", "waves", "left-heavy", "light", "stress")
MOVEMENTS = {"N": ("E", "S", "W"), "E": ("S", "W", "N"),
             "S": ("W", "N", "E"), "W": ("N", "E", "S")}


class DemandModel:
    def __init__(self, scenario):
        scenario = Path(scenario)
        config = ET.parse(scenario).getroot()
        self.static = ET.Element("routes")
        self.flows = []
        for filename in config.find("input/route-files").get("value").split(","):
            for child in ET.parse(scenario.parent / filename.strip()).getroot():
                if child.tag == "flow":
                    self.flows.append(dict(child.attrib))
                elif child.tag not in ("vehicle", "trip"):
                    self.static.append(deepcopy(child))
        self.routes = {tuple(item.get("edges").split()): item.get("id")
                       for item in self.static.findall("route")}
        if len(self.flows) != 4 or {flow.get("id") for flow in self.flows} != {f"flow_{d}" for d in MOVEMENTS}:
            raise ValueError("Profilurile cer cele patru fluxuri flow_N/E/S/W ale scenariilor livrate")

    def vehicles(self, profile, seed, duration, cycle=0):
        if profile not in PROFILES or duration <= 0:
            raise ValueError("Profil sau durată de cerere invalidă")
        result = []
        for flow in self.flows:
            direction = flow["id"][-1]
            choices = [(self.routes[(f"{direction}_in", f"{target}_out")], index)
                       for index, target in enumerate(MOVEMENTS[direction])
                       if (f"{direction}_in", f"{target}_out") in self.routes]
            if profile == "left-heavy" and not any(index == 0 for _, index in choices):
                raise ValueError("Profilul left-heavy cere rute de stânga; folosește scenariul urban")
            weights = (0.45, 0.4, 0.15) if profile == "left-heavy" else (0.2, 0.6, 0.2)
            rng = random.Random(f"{seed}:{cycle}:{direction}")
            count = 0
            for begin, end, rate in intervals(profile, duration, direction, float(flow["period"])):
                begin = max(begin, float(flow.get("begin", 0)))
                if rate <= 0:
                    continue
                depart = begin if profile == "baseline" else begin + rng.expovariate(rate / 3600)
                while depart < end:
                    route = rng.choices([route for route, _ in choices],
                                        [weights[index] for _, index in choices])[0]
                    result.append(dict(
                        id=f"{flow['id']}.profile.{cycle}.{count}", route=route,
                        type=flow.get("type", "DEFAULT_VEHTYPE"),
                        depart=f"{cycle * duration + depart:.3f}",
                        departLane=flow.get("departLane", "best"),
                        departSpeed=flow.get("departSpeed", "max"),
                    ))
                    count += 1
                    depart += float(flow["period"]) if profile == "baseline" else rng.expovariate(rate / 3600)
        return sorted(result, key=lambda item: (float(item["depart"]), item["id"]))


def intervals(profile, duration, direction, period):
    if profile == "switching":
        north_south = direction in ("N", "S")
        yield 0, duration / 3, 900 if north_south else 150
        yield duration / 3, 2 * duration / 3, 150 if north_south else 900
        yield 2 * duration / 3, duration, 450
    elif profile == "waves":
        for begin in range(0, int(duration) + 1, 60):
            yield begin, min(begin + 20, duration), 900 if direction in ("N", "S") else 600
    else:
        rate = {"baseline": 3600 / period, "balanced": 450, "left-heavy": 3600 / period,
                "light": 90, "stress": 1100}[profile]
        yield 0, duration, rate


def write_demand(scenario, profile, seed, duration, destination):
    model = DemandModel(scenario)
    root = deepcopy(model.static)
    vehicles = model.vehicles(profile, seed, duration)
    for vehicle in vehicles:
        ET.SubElement(root, "vehicle", vehicle)
    ET.indent(root)
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)
    return len(vehicles)


class ProfileDemand:
    def __init__(self, scenario, profile, seed, duration, continuous):
        self.model = DemandModel(scenario)
        self.profile, self.seed, self.duration, self.continuous = profile, seed, duration, continuous
        self.cycle, self.index = 0, 0
        self.plan = self.model.vehicles(profile, seed, duration)
        self.directory = tempfile.TemporaryDirectory(prefix="demand-", dir=Path(scenario).parent / "results")
        self.static_file = Path(self.directory.name) / "routes.xml"
        ET.ElementTree(self.model.static).write(self.static_file, encoding="utf-8", xml_declaration=True)

    def extend(self, connection):
        horizon = connection.simulation.getTime() + connection.simulation.getDeltaT()
        while True:
            if self.index >= len(self.plan):
                if not self.continuous or horizon < (self.cycle + 1) * self.duration:
                    return
                self.cycle += 1
                self.index = 0
                self.plan = self.model.vehicles(self.profile, self.seed, self.duration, self.cycle)
                continue
            vehicle = self.plan[self.index]
            if float(vehicle["depart"]) >= horizon:
                return
            connection.vehicle.add(vehicle["id"], vehicle["route"], typeID=vehicle["type"],
                                   depart=vehicle["depart"], departLane=vehicle["departLane"],
                                   departSpeed=vehicle["departSpeed"])
            self.index += 1

    def close(self):
        self.directory.cleanup()
