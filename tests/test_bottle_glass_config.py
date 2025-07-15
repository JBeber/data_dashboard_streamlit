import tempfile
import yaml
import os, pytest

@pytest.fixture
def bottle_to_glass_map():
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    return config.get("bottle_to_glass_map", {})

def test_mapping_matches_reference(bottle_to_glass_map):
    tempmapping = {
        "Barbera D'Asti - Vigne Vecchie": "Glass Barbera D'Asti - Vigne Vecchie",
        "Primitivo Sin - Vigne Vecchie": "Glass Primitivo Sin - Vigne Vecchie",
        "Pinot Grigio - Villa Loren": "Glass Pinot Grigio - Villa Loren",
        "Chardonnay - Tenuta Maccan": "Glass Chardonnay - Tenuta Maccan",
        "Moscato D'Asti - La Morandina": "Glass Moscato D'Asti - La Morandina",
        "Gavi Masera - Stefano Massone": "Glass Gavi - Masera",
        "Negramaro Rosato Soul - Vigne Vecchie": "Glass Rosato Soul - Vigne Vecchie",
        "Gattinara Rosato Bricco Lorella - Antoniolo": "Glass Gattinara Rosato - Antoniolo Bricco Lorella",
        "Prosecco Brut - Castel Nuovo del Garda": "Glass Prosecco Brut - Castel Nuovo del Garda",
        "Prosecco Rose - Castel Nuovo del Garda": "Glass Prosecco Rosato - Castel Nuovo del Garda",
        "Trento DOC - Maso Bianco - Seiterre": "Glass Trento DOC - Maso Bianco - Seiterre",
        "Nebbiolo - Vigne Vecchie": "Glass Nebbiolo - Vigne Vecchie",
        "Chianti Superiore - Banfi": "Glass Chianti Superiore - Banfi",
        "Nerello Mascalese - Vento di Mare": "Glass Nerello Mascalese - Vento di Mare"
    }

    # Now load the mapping using your loader
    loaded_mapping = bottle_to_glass_map
    assert loaded_mapping == tempmapping


def test_mapping_missing_key(bottle_to_glass_map):
    # Should raise KeyError if key not found when using []
    with pytest.raises(KeyError):
        _ = bottle_to_glass_map["Nonexistent Bottle"]

def test_mapping_get_method(bottle_to_glass_map):
    # Should return None if key not found when using get()
    assert bottle_to_glass_map.get("Nonexistent Bottle") is None

def test_mapping_is_one_to_one(bottle_to_glass_map):
    # Each glass name should be unique (one-to-one mapping)
    glass_names = list(bottle_to_glass_map.values())
    assert len(glass_names) == len(set(glass_names))