"""
Configuration management service for Kindle TTS Reader.
Allows users to save, load, and manage multiple configuration profiles.
"""
import json
import os
from typing import Dict, List, Optional
from datetime import datetime


class ConfigManager:
    """Manages saving and loading of user configuration profiles."""
    
    def __init__(self, config_file: str = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_file: Path to the JSON file storing configurations.
                        Defaults to src/resources/userSettings.json
        """
        if config_file is None:
            base_dir = os.path.dirname(os.path.dirname(__file__))
            config_file = os.path.join(base_dir, "resources", "userSettings.json")
        
        self.config_file = config_file
        self._ensure_config_file()
    
    def _ensure_config_file(self):
        """Ensure the config file and directory exist."""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        if not os.path.exists(self.config_file):
            # Create initial structure
            initial_data = {
                "auto_load_config": None,
                "configs": {}
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, indent=2)
    
    def save_config(self, config_name: str, config_data: Dict) -> bool:
        """
        Save a configuration profile.
        
        Args:
            config_name: Name for this configuration profile
            config_data: Dictionary containing all settings
            
        Returns:
            True if successful, False otherwise
        """
        try:
            data = self._load_data()
            
            # Add metadata
            config_data["_saved_at"] = datetime.now().isoformat()
            config_data["_config_name"] = config_name
            
            # Save the config
            data["configs"][config_name] = config_data
            
            self._save_data(data)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def load_config(self, config_name: str) -> Optional[Dict]:
        """
        Load a configuration profile by name.
        
        Args:
            config_name: Name of the configuration to load
            
        Returns:
            Configuration dictionary if found, None otherwise
        """
        try:
            data = self._load_data()
            return data["configs"].get(config_name)
        except Exception as e:
            print(f"Error loading config: {e}")
            return None
    
    def delete_config(self, config_name: str) -> bool:
        """
        Delete a configuration profile.
        
        Args:
            config_name: Name of the configuration to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            data = self._load_data()
            
            if config_name in data["configs"]:
                del data["configs"][config_name]
                
                # If this was the auto-load config, clear it
                if data.get("auto_load_config") == config_name:
                    data["auto_load_config"] = None
                
                self._save_data(data)
                return True
            return False
        except Exception as e:
            print(f"Error deleting config: {e}")
            return False
    
    def list_configs(self) -> List[str]:
        """
        Get a list of all saved configuration names.
        
        Returns:
            List of configuration names
        """
        try:
            data = self._load_data()
            return list(data["configs"].keys())
        except Exception:
            return []
    
    def set_auto_load(self, config_name: Optional[str]) -> bool:
        """
        Set which configuration should auto-load on startup.
        
        Args:
            config_name: Name of config to auto-load, or None to disable
            
        Returns:
            True if successful, False otherwise
        """
        try:
            data = self._load_data()
            
            # Verify config exists if not None
            if config_name is not None and config_name not in data["configs"]:
                return False
            
            data["auto_load_config"] = config_name
            self._save_data(data)
            return True
        except Exception as e:
            print(f"Error setting auto-load: {e}")
            return False
    
    def get_auto_load(self) -> Optional[str]:
        """
        Get the name of the configuration set to auto-load.
        
        Returns:
            Configuration name or None if no auto-load is set
        """
        try:
            data = self._load_data()
            return data.get("auto_load_config")
        except Exception:
            return None
    
    def get_auto_load_config(self) -> Optional[Dict]:
        """
        Get the configuration data for the auto-load config.
        
        Returns:
            Configuration dictionary or None if no auto-load is set
        """
        auto_load_name = self.get_auto_load()
        if auto_load_name:
            return self.load_config(auto_load_name)
        return None
    
    def _load_data(self) -> Dict:
        """Load the entire configuration data from file."""
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_data(self, data: Dict):
        """Save the entire configuration data to file."""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def create_config_from_gui(gui_instance) -> Dict:
    """
    Extract current GUI settings into a configuration dictionary.
    
    Args:
        gui_instance: Instance of KindleTTSApp
        
    Returns:
        Dictionary containing all current settings
    """
    config = {
        "engine": gui_instance.tts_engine_var.get(),
        "model": gui_instance.model_var.get(),
        "voice": gui_instance.voice_var.get(),
        "rate": gui_instance.rate_var.get(),
        "volume": gui_instance.volume_var.get(),
        "sample": gui_instance.sample_var.get(),
        "page_delay": gui_instance.page_delay_var.get(),
        "device": gui_instance.device_var.get(),
        "window": gui_instance.selected_window_var.get(),
    }
    return config


def apply_config_to_gui(gui_instance, config: Dict):
    """
    Apply a configuration dictionary to the GUI.
    
    Args:
        gui_instance: Instance of KindleTTSApp
        config: Configuration dictionary to apply
    """
    # Set engine first as it affects other controls
    if "engine" in config:
        gui_instance.tts_engine_var.set(config["engine"])
        gui_instance._on_engine_changed()
    
    # Set model
    if "model" in config:
        gui_instance.model_var.set(config["model"])
        gui_instance._on_model_changed()
    
    # Set voice/speaker
    if "voice" in config:
        gui_instance.voice_var.set(config["voice"])
        gui_instance._on_voice_changed()
    
    # Set other parameters
    if "rate" in config:
        gui_instance.rate_var.set(config["rate"])
    
    if "volume" in config:
        gui_instance.volume_var.set(config["volume"])
    
    if "sample" in config:
        gui_instance.sample_var.set(config["sample"])
    
    if "page_delay" in config:
        gui_instance.page_delay_var.set(config["page_delay"])
    
    if "device" in config:
        gui_instance.device_var.set(config["device"])
    
    if "window" in config:
        gui_instance.selected_window_var.set(config["window"])
