import pytest
from bathysphere_graph.drivers import Ingress, count, connect
from bathysphere_graph.catalog import Collections, Catalogs
from ..secrets import NEO4J_AUTH


class TestCatalogExtensionAPI:

    @staticmethod
    @pytest.mark.dependency()
    def test_create_provider(create_entity, graph):
        """Create non-core provider"""
        cls = Ingress.__name__
        response = create_entity(
            cls,
            {
                "entityClass": cls,
                "name": "Maine Aquaculture Association",
                "description": "",
                "url": ""
            }
        )
        data = response.get_json()
        assert response.status_code == 200, data
        assert count(graph, cls=cls) > 0

    @staticmethod
    @pytest.mark.dependency(depends=["TestCatalogExtensionAPI::test_create_provider"])
    def test_create_collection(create_entity, graph):
        """Create collection."""
        cls = Collections.__name__
        response = create_entity(
            cls,
            {
                "entityClass": cls,
                "title": "Oysters",
                "description": "Oyster growth simulations",
                "license": "",
                "version": 1,
                "keywords": "oysters,aquaculture,Maine,ShellSIM",
                "providers": None
            }
        )
        data = response.get_json()
        assert response.status_code == 200, data
        assert count(graph, cls=cls) > 0
        payload = data.get("value")
        obj_id = payload.get("@iot.id")

    @staticmethod
    @pytest.mark.dependency(depends=["TestCatalogExtensionAPI::test_create_collection"])
    def test_create_catalog(create_entity, graph):
        """Test database is empty."""
        cls = Catalogs.__name__
        response = create_entity(
            cls,
            {
                "entityClass": cls,
                "title": "neritics-bivalve-simulations",
                "description": "Bivalve growth experiments with Neritics API formats.",
            }
        )
        data = response.get_json()
        assert response.status_code == 200, data
        assert count(graph, cls=cls) > 0
        payload = data.get("value")
        obj_id = payload.get("@iot.id")



