class AquariteDataService:
    """Get and update the latest data."""

    def __init__(self, hass, api, pool_id):
        """Initialize the data object."""
        self.api = api
        self.pool_id = pool_id
        self.hass = hass
        self.coordinator = None

    @property
    def update_interval(self):
        return UPDATE_DELAY

    async def async_update_data(self):
        """Update the data."""
        try:
            self.roomdata = await self.hass.async_add_executor_job(
                self.api.get_rooms, self.location_id
            )
        except KeyError as ex:
            raise UpdateFailed("Missing overview data, skipping update") from ex

    async def async_setup(self):
        """Set up the coordinator."""
        self.coordinator = DataUpdateCoordinator(
            self.hass,
            _LOGGER,
            name="AquariteDataService",
            update_method=self.async_update_data,
            update_interval=self.update_interval,
        )

    def get_value(self, value_path):
        """Get the value from the data."""
        return snapshot.get(value_path)
