from sc_kpm import ScModule
from .PlanetDataAgent import PlanetDataAgent


class PlanetDataModule(ScModule):
    def __init__(self):
        super().__init__(PlanetDataAgent())
