from typing import List
from voltrail_core.models import Coordinate, RouteSegment, RoadClass
from voltrail_core.routing.protocols import RoutingProvider

class FixtureRoutingProvider(RoutingProvider):
    """
    Returns a predefined route for testing purposes without needing a real OSRM server.
    """
    def __init__(self, segments: List[RouteSegment] = None):
        if segments is None:
            # Default mock 50km highway route
            self.segments = [
                RouteSegment(
                    distance_m=50000.0,
                    start=Coordinate(21.0285, 105.8542), # Hanoi
                    end=Coordinate(20.432, 105.9), # South
                    elevation_gain_m=0.0,
                    grade=0.0,
                    speed_limit_mps=25.0,
                    expected_speed_mps=25.0,
                    road_class=RoadClass.HIGHWAY
                )
            ]
        else:
            self.segments = segments

    def get_route(self, origin: Coordinate, destination: Coordinate) -> List[RouteSegment]:
        # Ignore origin and destination, just return the fixture
        return self.segments
