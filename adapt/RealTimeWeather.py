# -*- coding: utf-8 -*-
"""
@author: Musavir Bashir
"""

import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry
import numpy as np
import math

class RealTimeWeather:
    def __init__(self):
        # Setup the Open-Meteo API client with cache and retry on error
        cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        self.openmeteo = openmeteo_requests.Client(session=retry_session)
        
        # Approximate standard atmosphere mapping (Altitude m -> Pressure hPa)
        # Airships usually cruise between 950 hPa (500m) and 850 hPa (1500m)
        self.pressure_levels = [975, 950, 925, 900, 850, 800]
        
    def _alt_to_pressure_level(self, altitude_m):
        # Very rough approximation: P = 1013.25 * (1 - 2.25577e-5 * h)**5.25588
        # We find the closest standard level available in the API
        p_approx = 1013.25 * (1 - 2.25577e-5 * altitude_m)**5.25588
        # Find closest level in our list
        closest = min(self.pressure_levels, key=lambda x: abs(x - p_approx))
        return closest

    def get_winds_aloft(self, lat, lon, altitude_m, time_offset_hours=0):
        """
        Fetches wind speed (m/s) and direction (deg) at the specific location and altitude.
        """
        level = self._alt_to_pressure_level(altitude_m)
        level_str = f"{level}hPa"
        
        url = "https://api.open-meteo.com/v1/forecast"
        
        # Variables: u and v components allow exact vector math
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": [f"wind_speed_{level_str}", f"wind_direction_{level_str}"],
            "forecast_days": 1
        }
        
        try:
            responses = self.openmeteo.weather_api(url, params=params)
            response = responses[0]
            
            # Process hourly data
            hourly = response.Hourly()
            
            # Extract specific hour (simple index logic)
            # In a real app, you would match the exact timestamp
            #idx = min(int(time_offset_hours), 23)
            idx = int(np.clip(np.round(time_offset_hours), 0, 23)) #round instead of floor

            
            # The API returns numpy arrays
            speed_arr = hourly.Variables(0).ValuesAsNumpy()
            dir_arr   = hourly.Variables(1).ValuesAsNumpy()
            
            w_speed = float(speed_arr[idx])
            w_dir   = float(dir_arr[idx])
            
            return {
                "speed_mps": w_speed, 
                "dir_deg": w_dir, 
                "pressure_level": level
            }
            
        except Exception as e:
            print(f"Weather API Error: {e}")
            return {"speed_mps": 0.0, "dir_deg": 0.0, "pressure_level": level}

# --- Quick Test ---
if __name__ == "__main__":
    wx = RealTimeWeather()
    # Test: Montreal at 1000m altitude
    data = wx.get_winds_aloft(45.5017, -73.5673, 1000.0)
    print(f"Montreal Winds at ~1000m (Level {data['pressure_level']}hPa):")
    print(f"Speed: {data['speed_mps']:.1f} m/s")
    print(f"Direction: {data['dir_deg']:.1f} deg (From)")