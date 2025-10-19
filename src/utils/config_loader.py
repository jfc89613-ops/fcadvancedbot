import yaml
from pydantic import BaseModel, ValidationError

class Config(BaseModel):
    # Define your configuration model fields here
    setting1: str
    setting2: int
    setting3: bool

    class Config:
        # Additional configuration for Pydantic
        validate_assignment = True


def load_config(file_path: str) -> Config:
    """Load and parse a YAML configuration file with validation."""
    try:
        with open(file_path, 'r') as file:
            config_data = yaml.safe_load(file)
        return Config(**config_data)
    except FileNotFoundError:
        raise Exception(f"Configuration file {file_path} not found.")
    except ValidationError as e:
        raise Exception(f"Configuration validation error: {e}")
    except Exception as e:
        raise Exception(f"An error occurred while loading the configuration: {e}")
