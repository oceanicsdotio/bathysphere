from ..sensing import Locations, FeaturesOfInterest


class Cells(Locations):

    def __init__(self, **kwargs):
        Locations.__init__(self, **kwargs)

        self.solid = None  # element contains solid boundary node
        self.open = None  # element contains open boundary node
        self.porosity = None
        self.area = None


class Nodes(Locations):

    _neighbors = None  # nodes sharing an edge with given node -- set in self.adjacency()
    _parents = None  # triangles containing given node -- set in self.adjacency()

    def __init__(self, **kwargs):
        Locations.__init__(self, **kwargs)

        self.solid = None  # solid boundary mask -- set in self.adjacency()
        self.area = None  # planar area of control volumes -- set_areas()
        self.parent_area = None  # total area of parent elements -- set_areas()
        self.elevation = None
        self.wet = None
        self.open = None


class Mesh(FeaturesOfInterest):

    _model = None  # regression model handle for interpolating data to the grid
    _triang = None  # triangulation object reference
    _host = None  # tri finder object reference

    def __init__(self, path=None, **kwargs):
        FeaturesOfInterest.__init__(self, **kwargs)
        self.data = path

        self.layers = 0
        self.nodes = 0
        self.cells = 0
        self.fit = None  # r-squared value of the last trend surface fit

    def statistics(self):
        pass


mesh_models = {
    Cells,
    Nodes,
    Mesh
}