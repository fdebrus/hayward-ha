# aioaquarite

Async Python client for the Hayward Aquarite pool API.

This library provides a standalone API client for interacting with Hayward Aquarite pool equipment via the Hayward cloud service. It is designed to be used as the backend for the [Home Assistant Aquarite integration](https://github.com/fdebrus/hayward-ha).

## Installation

```bash
pip install aioaquarite
```

## Usage

```python
import aiohttp
from aioaquarite import AquariteAuth, AquariteClient

async with aiohttp.ClientSession() as session:
    # Authenticate
    auth = AquariteAuth(session, "user@example.com", "password")
    await auth.authenticate()

    # Create client
    client = AquariteClient(auth)

    # List pools
    pools = await client.get_pools()

    # Fetch pool data
    for pool_id, pool_name in pools.items():
        data = await client.fetch_pool_data(pool_id)
        temperature = AquariteClient.get_value(data, "main.temperature")
        print(f"{pool_name}: {temperature}°C")

    # Subscribe to real-time updates
    def on_update(data):
        print("Pool updated:", data.get("main", {}).get("temperature"))

    watch = await client.subscribe_pool(pool_id, on_update)

    # Set a value
    await client.set_value(pool_id, "filtration.mode", 1)

    # Cleanup
    watch.unsubscribe()
```

## License

MIT
