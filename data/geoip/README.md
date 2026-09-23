# GeoLite2-City.mmdb

1. Copy your MaxMind file here as **`GeoLite2-City.mmdb`** (exact name).
2. In `.env`:
   ```env
   GEOLITE2_CITY_PATH=/data/geoip/GeoLite2-City.mmdb
   GEOLITE2_HOST_PATH=./data/geoip/GeoLite2-City.mmdb
   ```
   If the file lives elsewhere on the host, set `GEOLITE2_HOST_PATH` to that absolute path.
3. Recreate app (required after adding the file or changing mount):
   ```bash
   docker compose up -d --force-recreate app
   ```
4. Verify:
   ```bash
   docker compose exec app ma-geo-enrich --check
   ```

**Note:** If you start Compose before the `.mmdb` file exists, Docker may create an empty **directory** named `GeoLite2-City.mmdb`. Remove it and place the real file, then recreate the app container.
