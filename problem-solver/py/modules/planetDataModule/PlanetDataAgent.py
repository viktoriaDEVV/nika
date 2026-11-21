import json
import math
from pathlib import Path

from sc_client.client import set_link_contents, template_search
from sc_client.models import ScLinkContent, ScLinkContentType
from sc_client.constants import sc_types
from sc_client.constants.common import ScEventType
from sc_client.models import ScAddr, ScTemplate

from sc_kpm import ScAgent, ScKeynodes, ScResult
from sc_kpm.utils import (
    check_edge,
    create_edge,
    create_link,
    create_node,
    create_norole_relation,
    delete_edges,
    get_edge,
    get_element_by_norole_relation,
)


class PlanetDataAgent(ScAgent):
    """Агент адаптации знаний: загружает данные о планетах из локального JSON,
    обновляет БЗ, выводит тип планеты и плотность, считает планеты по типам."""

    def __init__(self):
        super().__init__("concept_message_about_planet_data", ScEventType.ADD_OUTGOING_EDGE)
        self.data_path = Path(__file__).parent / "planets.json"

    def on_event(self, event_element: ScAddr, event_edge: ScAddr, message: ScAddr) -> ScResult:
        self.logger.info("PlanetDataAgent started")
        try:
            self.run(message)
            self.logger.info("PlanetDataAgent finished successfully")
            return ScResult.OK
        except Exception as exception:  # noqa: BLE001
            self.logger.exception("PlanetDataAgent failed: %s", exception)
            return ScResult.ERROR

    def run(self, message: ScAddr) -> None:
        data = json.loads(self.data_path.read_text(encoding="utf-8"))

        nrel_distance = ScKeynodes.resolve("nrel_distance_from_sun", sc_types.NODE_CONST_NOROLE)
        nrel_diameter = ScKeynodes.resolve("nrel_equatorial_diameter", sc_types.NODE_CONST_NOROLE)
        nrel_satellites = ScKeynodes.resolve("nrel_number_of_satellites", sc_types.NODE_CONST_NOROLE)
        nrel_mass = ScKeynodes.resolve("nrel_mass", sc_types.NODE_CONST_NOROLE)
        nrel_density = ScKeynodes.resolve("nrel_density", sc_types.NODE_CONST_NOROLE)
        nrel_text = ScKeynodes.resolve("nrel_sc_text_translation", sc_types.NODE_CONST_NOROLE)
        nrel_authors = ScKeynodes.resolve("nrel_authors", sc_types.NODE_CONST_NOROLE)
        nrel_reply = ScKeynodes.resolve("nrel_reply", sc_types.NODE_CONST_NOROLE)
        nrel_sequence = ScKeynodes.resolve("nrel_message_sequence", sc_types.NODE_CONST_NOROLE)
        rrel_last = ScKeynodes.resolve("rrel_last", sc_types.NODE_CONST_ROLE)

        concept_message = ScKeynodes.resolve("concept_message", sc_types.NODE_CONST_CLASS)
        concept_text_file = ScKeynodes.resolve("concept_text_file", sc_types.NODE_CONST_CLASS)
        concept_atomic = ScKeynodes.resolve("concept_atomic_message", sc_types.NODE_CONST_CLASS)
        concept_terrestrial = ScKeynodes.resolve("concept_terrestrial_planet", sc_types.NODE_CONST_CLASS)
        concept_gas = ScKeynodes.resolve("concept_gas_giant", sc_types.NODE_CONST_CLASS)
        concept_ice = ScKeynodes.resolve("concept_ice_giant", sc_types.NODE_CONST_CLASS)
        myself = ScKeynodes.resolve("myself", sc_types.NODE_CONST)

        counts = {"terrestrial": 0, "gas": 0, "ice": 0}
        densities = []
        loaded = 0

        for item in data:
            planet = ScKeynodes.resolve(item["idtf"], sc_types.NODE_CONST)
            if not planet.is_valid():
                self.logger.warning("Planet %s not found in KB", item["idtf"])
                continue
            loaded += 1

            self._set_value(planet, nrel_distance, str(item["distance_au"]))
            self._set_value(planet, nrel_diameter, str(item["diameter_km"]))
            self._set_value(planet, nrel_satellites, str(item["satellites"]))
            self._set_value(planet, nrel_mass, f"{item['mass_kg']:.4e}")

            if item["distance_au"] < 2:
                planet_class, key = concept_terrestrial, "terrestrial"
            elif item["distance_au"] < 10:
                planet_class, key = concept_gas, "gas"
            else:
                planet_class, key = concept_ice, "ice"
            if not check_edge(sc_types.EDGE_ACCESS_VAR_POS_PERM, planet_class, planet):
                create_edge(sc_types.EDGE_ACCESS_CONST_POS_PERM, planet_class, planet)
            counts[key] += 1

            radius_m = item["diameter_km"] * 1000 / 2
            volume_m3 = 4 / 3 * math.pi * radius_m ** 3
            density = item["mass_kg"] / volume_m3
            self._set_value(planet, nrel_density, f"{density:.0f}")
            densities.append((item["name"], density))

        densest_name, densest_value = max(densities, key=lambda pair: pair[1]) if densities else ("—", 0)
        text = (
            f"Загружено {loaded} планет: земной группы — {counts['terrestrial']}, "
            f"газовых гигантов — {counts['gas']}, ледяных — {counts['ice']}. "
            f"Самая плотная — {densest_name} ({densest_value:.0f} кг/м³)."
        )
        self.logger.info("PlanetDataAgent answer: %s", text)
        self._reply(message, text, concept_message, concept_atomic, concept_text_file, nrel_text, nrel_authors,
                    nrel_reply, nrel_sequence, rrel_last, myself)

    @staticmethod
    def _set_value(planet: ScAddr, relation: ScAddr, value: str) -> None:
        link = get_element_by_norole_relation(planet, relation)
        if link.is_valid():
            set_link_contents(ScLinkContent(value, ScLinkContentType.STRING, link))
        else:
            create_norole_relation(planet, create_link(value), relation)

    def _reply(self, message: ScAddr, text: str, concept_message: ScAddr, concept_atomic: ScAddr,
               concept_text_file: ScAddr, nrel_text: ScAddr, nrel_authors: ScAddr, nrel_reply: ScAddr,
               nrel_sequence: ScAddr, rrel_last: ScAddr, myself: ScAddr) -> None:
        reply = create_node(sc_types.NODE_CONST)
        create_edge(sc_types.EDGE_ACCESS_CONST_POS_PERM, concept_message, reply)
        create_edge(sc_types.EDGE_ACCESS_CONST_POS_PERM, concept_atomic, reply)

        link = create_link(text)
        translation = create_node(sc_types.NODE_CONST)
        create_norole_relation(translation, reply, nrel_text)
        create_edge(sc_types.EDGE_ACCESS_CONST_POS_PERM, translation, link)
        create_edge(sc_types.EDGE_ACCESS_CONST_POS_PERM, concept_text_file, link)
        create_norole_relation(reply, myself, nrel_authors)
        create_norole_relation(message, reply, nrel_reply)

        chat = self._find_chat(message, rrel_last)
        if not chat.is_valid():
            self.logger.warning("Chat not found, reply is not added to dialog")
            return

        message_edge = get_edge(chat, message, sc_types.EDGE_ACCESS_VAR_POS_PERM)
        if message_edge.is_valid():
            delete_edges(rrel_last, message_edge, sc_types.EDGE_ACCESS_VAR_POS_PERM)

        reply_edge = create_edge(sc_types.EDGE_ACCESS_CONST_POS_PERM, chat, reply)
        create_edge(sc_types.EDGE_ACCESS_CONST_POS_PERM, rrel_last, reply_edge)
        if message_edge.is_valid():
            create_norole_relation(message_edge, reply_edge, nrel_sequence)

    @staticmethod
    def _find_chat(message: ScAddr, rrel_last: ScAddr) -> ScAddr:
        template = ScTemplate()
        template.triple_with_relation(
            (sc_types.NODE_VAR, "chat"),
            sc_types.EDGE_ACCESS_VAR_POS_PERM,
            message,
            sc_types.EDGE_ACCESS_VAR_POS_PERM,
            rrel_last,
        )
        result = template_search(template)
        return result[0].get("chat") if result else ScAddr(0)
