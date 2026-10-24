"""Pruebas del gestor de parqueadero (pendiente de implementar)."""

import unittest


class TestModelsSmoke(unittest.TestCase):
    """Verifica que los modelos base se importan y son instanciables."""

    def test_vehicle_defaults(self) -> None:
        from src.models.vehicle import Vehicle, VehicleState

        vehicle = Vehicle(id=1)
        self.assertEqual(vehicle.state, VehicleState.LLEGANDO)
        self.assertIsNone(vehicle.slot)


if __name__ == "__main__":
    unittest.main()
