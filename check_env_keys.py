import os
from dotenv import dotenv_values

env_path = os.path.join(os.path.dirname(__file__), '.env')
config = dotenv_values(env_path)

print(f"Keys found in {env_path}:")
for key in config.keys():
    print(key)
