try:
    from numpy import ndarray, array
except ImportError:
    pass


from pickle import dump, load
import attr
from bathysphere.future.utils import create_fields

from .settling import Settling
from ...chemistry.organic import OXYGEN, CARBON
from ...chemistry.nutrient import Nitrogen, NITROGEN, SILICA, PHOSPHOROUS

NUTRIENTS = (NITROGEN, SILICA, PHOSPHOROUS)

from .chemistry.nutrient import SILICATE, SILICA, PHOSPHATE

POM = "POM"
PIM = "PIM"
VS = "VS"
SEDT = "SEDT"
PMT = "PMT"
NET = "NET"
BAST = "BAST"
RATIO_CN = "CTONCSO"
RATIO_CP = "CTOPCSO"

DEFAULT_CONFIG = {
    RATIO_CP: 0.0,  # carbon to phosphorus ratio of cso solids
    RATIO_CN: 0.0,  # CARBON TO NITROGEN RATIO OF CSO SOLIDS
    "KAT": 1.024,  # TEMPERATURE CORRECTION COEFFICIENT FOR ATMOSPHERIC REAERATION
    VS+BAST: 1.027,  # TEMPERATURE CORRECTION
    VS+POM: 1.0,  # PARTICULATE ORGANIC MATTER SETTLING RATE          M/DAY
    VS+PMT: 1.027,  # TEMPERATURE CORRECTION
    VS+SEDT: 1.027,  # TEMPERATURE CORRECTION FOR DEPOSITION TO SEDIMENT
    VS+PIM: 0.0,  # SETTLING RATE FOR PHOSPHOURS/SILICA SORBED TO SS     M/DAY
    "KECONST": 0.001  # base chl corrected extinction coefficient (when KEOPT is 0 or 2)
}


class Settling:

    sediment = None
    config = DEFAULT_CONFIG

    def base(self, anomaly):
        return self.config["VSPMT"] ** anomaly

    def settling(self, carbon, phosphorous, silica, phytoplankton, anomaly, mesh=None, conversion=0.001):
        """
        Move particulate mass due to settling

        :param mesh: mesh instance
        :param anomaly: temperature anomaly

        :return:
        """

        assert all(each.settling(mesh, systems, self.sediment) for each in phytoplankton)

        base = self.settling * mesh.nodes.area
        correction = self.config[VS+SEDT] ** anomaly

        assert phosphorous._adsorbed(base, conversion, self.sediment, (PHOSPHATE, PHOSPHATE))
        assert self._particulate_organics(base, correction, systems, carbon, phosphorous, silica)

        corr = self.config[VS + NET] * correction
        assert self.sediment.conversion(key, carbon._solids(**kwargs), corr)

        if self.sediment is not None:
            self.sediment.flux()

    def _adsorbed(self, base, phosphorous, silica, sediment=None):
        """

        :param base: base rate
        :param phosphorous: phosphorous system
        :param silica: silica system
        :param sediment: optional sediment instance

        :return: success
        """
        flux = base * self.config[VS+PIM]
        a = phosphorous.adsorbed(flux, PHOSPHATE, PHOSPHATE, sediment)
        b = silica.adsorbed(flux, SILICA, SILICATE, sediment)

        return a and b

    def _particulate_organics(self, base, correction, systems, carbon, phosphorous, silica):
        """
        :param base:
        :param correction:
        :param systems:

        :return: success
        """
        flux = base * self.config[VS+POM]
        systems.deposit(base * correction, carbon.key, sediment=self.sediment)

        corr = correction / self.config[VS+POM]
        delta = flux * self.config[VS+POM]

        assert silica._sinking(delta, corr, self.sediment)
        phosphorous._sinking(delta, corr, self.sediment)
        carbon._sinking(delta, corr, self.sediment)

        return True


class Reactor(dict, Settling):
    
    negatives = False
    config = None

    def __init__(self, systems, mesh=None, verb=False):
        """
        Encapsulates control parameters, and time step integration methods.

        :param mesh: mesh instance
        :param systems: list of chemical systems instances to track
        """

        dict.__init__(self, systems)
        Settling.__init__(self)
        self.verb = verb

        self.shape = (1, 1) if mesh is None else (mesh.nodes.n, mesh.layers.n)
        self.mesh = mesh

    def set(self, volume):
        """
        Transfer mass from difference equation to conservative arrays

        :param volume: volume to convert to/from concentration

        :return:
        """

        assert all(each.transfer(conversion=volume) for each in self.values())

    def integrate(self, anomaly, phyto_c=0.0, phyto_n=0.0, volume=1.0):
        """
        Perform internal chemistry steps

        :param anomaly: water temperature anomaly
        :param phyto_c: carbon from phytoplankton
        :param phyto_n: nitrogen from phytoplankton
        :return:
        """

        nutrients = [self[key] for key in self.keys() if key in NUTRIENTS]

        if self.verb:
            cls_names = [each.__class__.__name__ for each in nutrients]
            print("Difference equations for: Carbon, Oxygen,", ", ".join(cls_names))

        self._internal(anomaly, self[CARBON], self[OXYGEN], nutrients, phyto_c, phyto_n)

        if self.verb and volume.__class__ != ndarray:
            print("Making mass transfers, using volume="+str(volume))
        self.set(volume)

        return True

    @staticmethod
    def _internal(anomaly, carbon, oxygen, nutrients=(), phyto_c=0.0, phyto_n=0.0):
        """
        Update difference equations for internal, temperature-dependent chemistry.

        :param anomaly: temperature anomaly (usually T-20)
        :param carbon: required chemistry instance
        :param oxygen: required chemistry instance
        :param nutrients: optional list of nutrients to track
        :param phyto_c: carbon supplied by biology
        :param phyto_n: nitrogen supplied by biology

        :return: success
        """

        limit = carbon.integrate(anomaly, oxygen, phyto_c)  # available carbon as proxy, consumes oxygen
        assert oxygen.integrate(limit, anomaly)  # oxygen consumption

        assert all(nutrient.mineralize(limit, anomaly) for nutrient in nutrients)

        for each in nutrients:
            if each.__class__ == Nitrogen:
                assert each.integrate(oxygen, carbon, phyto_n, anomaly)  # consumes oxygen and carbon
                break

        return True
