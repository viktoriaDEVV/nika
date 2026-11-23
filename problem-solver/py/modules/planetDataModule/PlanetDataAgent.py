import json
import math
from pathlib import Path

from sc_client.client import set_link_contents, template_search
from sc_client.constants import sc_types
from sc_client.constants.common import ScEventType
from sc_client.models import ScAddr, ScLinkContent, ScLinkContentType, ScTemplate

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
    """Агент адаптации знаний о планетах.

    Загружает данные из локального JSON, создаёт отсутствующие экземпляры,
    обновляет существующие, выводит тип и плотность, считает аналитику.
    """

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
        nrel_main_idtf = ScKeynodes.resolve("nrel_main_idtf", sc_types.NODE_CONST_NOROLE)
        nrel_text = ScKeynodes.resolve("nrel_sc_text_translation", sc_types.NODE_CONST_NOROLE)
        nrel_authors = ScKeynodes.resolve("nrel_authors", sc_types.NODE_CONST_NOROLE)
        nrel_reply = ScKeynodes.resolve("nrel_reply", sc_types.NODE_CONST_NOROLE)
        nrel_sequence = ScKeynodes.resolve("nrel_message_sequence", sc_types.NODE_CONST_NOROLE)
        rrel_last = ScKeynodes.resolve("rrel_last", sc_types.NODE_CONST_ROLE)
        lang_ru = ScKeynodes.resolve("lang_ru", sc_types.NODE_CONST_CLASS)

        concept_message = ScKeynodes.resolve("concept_message", sc_types.NODE_CONST_CLASS)
        concept_atomic = ScKeynodes.resolve("concept_atomic_message", sc_types.NODE_CONST_CLASS)
        concept_text_file = ScKeynodes.resolve("concept_text_file", sc_types.NODE_CONST_CLASS)
        concept_planet = ScKeynodes.resolve("concept_planet", sc_types.NODE_CONST_CLASS)
        concept_terrestrial = ScKeynodes.resolve("concept_terrestrial_planet", sc_types.NODE_CONST_CLASS)
        concept_gas = ScKeynodes.resolve("concept_gas_giant", sc_types.NODE_CONST_CLASS)
        concept_ice = ScKeynodes.resolve("concept_ice_giant", sc_types.NODE_CONST_CLASS)
        concept_dwarf = ScKeynodes.resolve("concept_dwarf_planet", sc_types.NODE_CONST_CLASS)
        myself = ScKeynodes.resolve("myself", sc_types.NODE_CONST)

        counts = {"terrestrial": 0, "gas": 0, "ice": 0, "dwarf": 0}
        loaded = 0
        created = 0
        rows = []

        for item in data:
            planet = ScKeynodes.get(item["idtf"])
            is_new = not planet.is_valid()
            if is_new:
                planet = ScKeynodes.resolve(item["idtf"], sc_types.NODE_CONST)
                if not planet.is_valid():
                    self.logger.warning("Failed to create planet %s", item["idtf"])
                    continue
                created += 1
                self._add_name(planet, item["name"], nrel_main_idtf, lang_ru)
                create_edge(sc_types.EDGE_ACCESS_CONST_POS_PERM, concept_planet, planet)

            loaded += 1
            self._set_value(planet, nrel_distance, str(item["distance_au"]))
            self._set_value(planet, nrel_diameter, str(item["diameter_km"]))
            self._set_value(planet, nrel_satellites, str(item["satellites"]))
            self._set_value(planet, nrel_mass, f"{item['mass_kg']:.4e}")

            planet_class, key = self._infer_type(item, concept_terrestrial, concept_gas,
                                                 concept_ice, concept_dwarf)
            if not check_edge(sc_types.EDGE_ACCESS_VAR_POS_PERM, planet_class, planet):
                create_edge(sc_types.EDGE_ACCESS_CONST_POS_PERM, planet_class, planet)
            counts[key] += 1

            radius_m = item["diameter_km"] * 1000 / 2
            volume_m3 = 4 / 3 * math.pi * radius_m ** 3
            density = item["mass_kg"] / volume_m3
            self._set_value(planet, nrel_density, f"{density:.0f}")
            rows.append((item, density))

        text = self._make_answer(rows, counts, loaded, created)
        self.logger.info("PlanetDataAgent answer: %s", text)
        self._reply(message, text, concept_message, concept_atomic, concept_text_file, nrel_text,
                    nrel_authors, nrel_reply, nrel_sequence, rrel_last, myself)

    @staticmethod
    def _infer_type(item, terrestrial, gas, ice, dwarf):
        distance = item["distance_au"]
        diameter = item["diameter_km"]
        if distance < 2:
            return terrestrial, "terrestrial"
        if distance < 10:
            return (gas, "gas") if diameter > 50000 else (dwarf, "dwarf")
        if diameter > 30000:
            return ice, "ice"
        return dwarf, "dwarf"

    @staticmethod
    def _add_name(planet: ScAddr, name: str, nrel_main_idtf: ScAddr, lang_ru: ScAddr) -> None:
        link = create_link(name)
        create_norole_relation(planet, link, nrel_main_idtf)
        create_edge(sc_types.EDGE_ACCESS_CONST_POS_PERM, lang_ru, link)

    @staticmethod
    def _set_value(planet: ScAddr, relation: ScAddr, value: str) -> None:
        link = get_element_by_norole_relation(planet, relation)
        if link.is_valid():
            set_link_contents(ScLinkContent(value, ScLinkContentType.STRING, link))
        else:
            create_norole_relation(planet, create_link(value), relation)

    @staticmethod
    def _make_answer(rows, counts, loaded, created):
        if not rows:
            return "Не удалось загрузить данные о планетах."
        largest = max(rows, key=lambda pair: pair[0]["diameter_km"])
        smallest = min(rows, key=lambda pair: pair[0]["diameter_km"])
        most_satellites = max(rows, key=lambda pair: pair[0]["satellites"])
        densest = max(rows, key=lambda pair: pair[1])
        average_density = sum(pair[1] for pair in rows) / len(rows)
        created_part = f", создано новых — {created}" if created else ""
        return (
            f"Загружено {loaded} планет{created_part}: "
            f"земной группы — {counts['terrestrial']}, газовых гигантов — {counts['gas']}, "
            f"ледяных — {counts['ice']}, карликовых — {counts['dwarf']}. "
            f"Самая большая — {largest[0]['name']} ({largest[0]['diameter_km']} км), "
            f"самая маленькая — {smallest[0]['name']} ({smallest[0]['diameter_km']} км). "
            f"Больше всего спутников — {most_satellites[0]['name']} ({most_satellites[0]['satellites']}). "
            f"Средняя плотность — {average_density:.0f} кг/м³, самая плотная — {densest[0]['name']} ({densest[1]:.0f} кг/м³)."
        )

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
