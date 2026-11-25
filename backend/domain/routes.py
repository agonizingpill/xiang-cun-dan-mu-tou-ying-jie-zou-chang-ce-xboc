from domain.venues_api import router as venues
from domain.cue_tracks_api import router as cue_tracks
from domain.clock_calibrations_api import router as clock_calibrations
from domain.cue_clusters_api import router as cue_clusters
from domain.cue_routing_api import router as cue_routing

routers = (venues, cue_tracks, clock_calibrations, cue_clusters, cue_routing,)
