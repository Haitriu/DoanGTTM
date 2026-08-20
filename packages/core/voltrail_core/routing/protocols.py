from typing import Protocol, List
from voltrail_core.models import Coordinate, RouteSegment

class RoutingProvider(Protocol):
    def get_route(self, origin: Coordinate, destination: Coordinate) -> List[RouteSegment]:
        """
        Retrieves a route from origin to destination as a sequence of segments.
        This provides geometry, distance, speed limits, and road classes.
        """
        ...

class ElevationProvider(Protocol):
    def get_elevation(self, coordinates: List[Coordinate]) -> List[float]:
        """
        Retrieves elevation in meters for a sequence of coordinates.
        """
        ...
