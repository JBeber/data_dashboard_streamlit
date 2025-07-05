import pytest
import pandas as pd
from datetime import date
from modules.wine_bottles import WineDashboardData

# 1. A loader function for test data
def dummy_loader(file_name):
    # Simulate loading data as your real loader would
    # Here, we return a DataFrame with made-up data
    # The file-name parameter is not used in this dummy function
    # In a real scenario, you would read from a file collected from Drive
    return pd.DataFrame({
        'date': pd.date_range('2022-01-01', '2022-01-04'),
        'Menu Group': ['RETAIL WINE', 'Wine - Bottles', 'Wine - Glasses', 'Wine - Glasses'],
        'Menu Item': ['A', 'B', 'GlassA', 'GlassB'],
        'Item Qty': [2, 3, 4, 5]
    })

# 2. Fixtures: reusable setup for tests (pytest feature)
@pytest.fixture
def wine_data():
    # These are sample arguments for your class
    start = date(2022, 1, 1)
    end = date(2022, 1, 14)
    bottle_names = ['A', 'B']
    glass_names = ['GlassA', 'GlassB']
    bottle_to_glass_map = {'A': 'GlassA', 'B': 'GlassB'}
    # Return an instance of your class, using dummy_loader
    return WineDashboardData(start, end, dummy_loader, bottle_names, glass_names, bottle_to_glass_map)

# 3. Actual tests
def test_initialization(wine_data):
    # Check that the object is created and properties are set
    assert wine_data.start_date == date(2022, 1, 1)
    assert wine_data.end_date == date(2022, 1, 14)

def test_weekly_bottle_counts(wine_data):
    # Call the method you want to test
    df = wine_data.get_weekly_bottle_counts()
    # Assert the DataFrame is not empty
    assert not df.empty
    # Optionally, check columns or values
    assert 'bottle' in df.columns
    assert df['bottle_totals'].sum() > 0

def test_with_no_data():
    # Loader returns an empty DataFrame
    def empty_loader():
        return pd.DataFrame(columns=['date', 'Menu Group', 'Menu Item', 'Item Qty'])
    wine_data = WineDashboardData(date(2022,1,1), date(2022,1,7), empty_loader, ['A'], ['GlassA'], {'A':'GlassA'})
    df = wine_data.get_weekly_bottle_counts()
    # Should handle gracefully (not crash)
    assert df.empty

# Add more tests for other methods!