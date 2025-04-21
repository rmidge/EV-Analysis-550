import panel as pn
import pandas as pd
import geopandas as gpd
import hvplot.pandas
import numpy as np
from shapely.geometry import Point
import param
import holoviews as hv
from holoviews import opts
import os
import json
import folium

# Define global thresholds
THRESHOLDS = [0.45, 0.55, 0.65]

# Load data
census_gdf = gpd.read_file('analysis/data/gap_analysis_fixed.gpkg', layer='census')
stations_gdf = gpd.read_file('analysis/data/gap_analysis_fixed.gpkg', layer='stations')

try:
    # City boundary
    philly_boundary = gpd.read_file('data/City_Limits.geojson')
except:
    # If not available, use the census tracts to create a boundary
    philly_boundary = gpd.GeoDataFrame(geometry=[census_gdf.geometry.union_all()], crs=census_gdf.crs)

# Analysis results from json
try:
    with open('data/analysis_results.json', 'r') as f:
        analysis_results = json.load(f)
except:
    # If not available, create a simplified version
    analysis_results = {
        'summary': {},
        'coverage': {},
        'gap_scores': {},
        'priority_areas': {},
        'weights': {},
    }

# Try to load demographic equity summary
try:
    demo_coverage = pd.read_csv('data/visualizations/demographic_equity_summary.csv')
except:
    demo_coverage = pd.DataFrame(columns=['buffer', 'variable', 'effect_size', 'ci_lower', 'ci_upper', 'p_value'])

# Pre-calculate some statistics for better performance
total_city_area = philly_boundary.to_crs("EPSG:2272").area.iloc[0] / (1609.34 ** 2)  # Convert to sq miles
total_tracts = len(census_gdf)

# Define the widgets first
charging_speed_filter = pn.widgets.Select(name='Charging Speed', options=['All', 'Level 1 (Slow)', 'Level 2 (Medium)', 'DC Fast (Rapid)'], value='All')
coverage_radius = pn.widgets.FloatSlider(name='Service Area Radius (miles)', start=0.1, end=2.0, step=0.1, value=0.5)
min_points = pn.widgets.IntSlider(name='Minimum Charging Points', start=1, end=10, step=1, value=1)

def filter_stations(charging_speed, min_points_val):
    filtered = stations_gdf.copy()
    
    if charging_speed != 'All':
        filtered = filtered[filtered['charging_speed'] == charging_speed]
    
    filtered = filtered[filtered['num_points'] >= min_points_val]
    
    return filtered

def calculate_statistics(stations):
    """Calculate statistics about the EV charging stations"""
    stats = {
        'Total Stations': len(stations),
        'Total Charging Points': stations['num_points'].sum(),
        'Average Points per Station': round(stations['num_points'].mean(), 1),
        'DC Fast Chargers': len(stations[stations['charging_speed'] == 'DC Fast (Rapid)']),
        'Level 2 Chargers': len(stations[stations['charging_speed'] == 'Level 2 (Medium)']),
        'Level 1 Chargers': len(stations[stations['charging_speed'] == 'Level 1 (Slow)'])
    }
    return stats

def create_coverage_analysis(stations, radius_miles):
    """Calculate coverage statistics for the given stations and radius"""
    # Convert radius to meters
    buffer_distance = radius_miles * 1609.34
    stations_buffered = stations.to_crs("EPSG:2272").buffer(buffer_distance)
    coverage_area = stations_buffered.union_all()
    
    coverage_area_sq_miles = coverage_area.area / (1609.34 ** 2)
    
    # Intersect with census tracts
    covered_tracts = census_gdf[census_gdf.to_crs("EPSG:2272").intersects(coverage_area)]
    
    coverage_stats = {
        'Service Area Radius': f"{radius_miles} miles",
        'Coverage Area': f"{round(coverage_area_sq_miles, 2)} sq mi",
        'City Coverage': f"{round(coverage_area_sq_miles / total_city_area * 100, 1)}%",
        'Census Tracts with Access': f"{len(covered_tracts)} of {total_tracts}",
        'Tract Coverage': f"{round(len(covered_tracts) / total_tracts * 100, 1)}%",
        'Population with Access': f"{covered_tracts['total_pop'].sum():,.0f} of {census_gdf['total_pop'].sum():,.0f}",
        'Population Coverage': f"{round(covered_tracts['total_pop'].sum() / census_gdf['total_pop'].sum() * 100, 1)}%",
        'Stations per Square Mile': f"{round(len(stations) / coverage_area_sq_miles, 2)}"
    }
    return coverage_stats

def create_dynamic_weights_panel():
    """Create a panel showing the dynamic weights used in the gap analysis"""
    try:
        weights = analysis_results.get('weights', {})
        
        # If weights are present, format them for display
        if weights:
            weights_md = "### Dynamic Weighting System\n\n"
            weights_md += "The gap score calculation dynamically adjusts weights based on observed disparities:\n\n"
            
            for key, value in weights.items():
                weights_md += f"- **{key.title()}**: {float(value)*100:.1f}%\n"
            
            weights_md += "\n*Weights are recalculated based on statistically significant disparities in the data.*"
        else:
            # Default weights if not available in results
            weights_md = "### Dynamic Weighting System\n\n"
            weights_md += "Default weights for gap score calculation:\n\n"
            weights_md += "- **Coverage**: 24.0%\n"
            weights_md += "- **Income**: 16.0%\n"
            weights_md += "- **Poverty**: 24.0%\n"
            weights_md += "- **Density**: 20.0%\n"
            weights_md += "- **Education**: 16.0%\n"
        
        return pn.pane.Markdown(weights_md)
    except Exception as e:
        print(f"Error creating weights panel: {e}")
        return pn.pane.Markdown("### Dynamic Weights\nError loading weights information.")

def create_methodology_modal():
    """Create a collapsible card explaining the methodology"""
    return pn.Card(
        pn.pane.Markdown(f"""
        ## Methodology
        
        ### Gap Score Calculation
        The gap score is calculated using a dynamic weighted system:
        
        1. **Coverage (24%)**
           - Walking distance buffer (0.25 miles / 1,320 ft)
           - Walking distance buffer (0.5 miles / 2,640 ft)
           - Walking distance buffer (0.75 miles / 3,960 ft)
           - Driving distance buffers (1, 2, and 3 miles)
        
        2. **Socioeconomic Factors (40%)**
           - Median household income (16%)
           - Poverty rate (24%)
        
        3. **Population Factors (20%)**
           - Population density (20%)
        
        4. **Development Indicators (16%)**
           - Education levels (16%)
        
        
        ### Priority Levels
        Areas are categorized using fixed thresholds:
        - Low Priority: gap_score ≤ {THRESHOLDS[0]}
        - Medium Priority: {THRESHOLDS[0]} < gap_score ≤ {THRESHOLDS[1]}
        - High Priority: {THRESHOLDS[1]} < gap_score ≤ {THRESHOLDS[2]}
        - Critical Priority: gap_score > {THRESHOLDS[2]}
        
        ### Data Sources
        - EV Charging Stations: OpenChargeMap API
        - Demographic Data: US Census Bureau (ACS 5-year estimates)
        - Street Network: OpenStreetMap
        """),
        title="Methodology",
        collapsed=True,  # Start collapsed
        width=300
    )

# Define the MapDashboard class
class MapDashboard(param.Parameterized):
    show_base_map = param.Boolean(default=True)
    show_gap_analysis = param.Boolean(default=True)
    show_coverage = param.Boolean(default=True)
    show_stations = param.Boolean(default=True)
    show_equity_analysis = param.Boolean(default=True)
    
    def __init__(self, stations, radius_miles, **params):
        super().__init__(**params)
        self.stations = stations
        self.radius_miles = radius_miles
        self.cached_layers = None
        self.analysis_results = analysis_results
        self.initialize_layers()
    
    def create_equity_analysis_panel(self):
        """Create a panel showing equity analysis results (simplified version)"""
        # Return an empty panel - effectively removing the summary
        return pn.pane.Markdown("")
    
    def initialize_layers(self):
        # Initialize map layers
        self.stations_wgs84 = self.stations.to_crs("EPSG:4326")
        self.census_wgs84 = census_gdf.to_crs("EPSG:4326")
        self.boundary_wgs84 = philly_boundary.to_crs("EPSG:4326")
        
        # Get map bounds
        minx, miny, maxx, maxy = self.boundary_wgs84.total_bounds
        padding = 0.005
        self.x_range = (minx - padding, maxx + padding)
        self.y_range = (miny - padding, maxy + padding)
        
        # Create equity panel if enabled
        if self.show_equity_analysis:
            self.equity_panel = self.create_equity_analysis_panel()
        
        self.create_all_layers()
    
    def create_all_layers(self):
        # Create base map layer
        self.base_map = self.boundary_wgs84.hvplot(
            geo=True,
            tiles='CartoLight',
            alpha=0.2,
            frame_height=650,
            frame_width=1000,
            xlim=self.x_range,
            ylim=self.y_range,
            project=False,
            legend=False,
            grid=False,        # Turn off grid lines
            xaxis=None,        # Hide x-axis
            yaxis=None         # Hide y-axis
        ).opts(
            active_tools=['wheel_zoom'],
            tools=['pan', 'wheel_zoom', 'reset'],
            show_grid=False,
            show_frame=True,
            frame_width=1,
            border_color='black'  
        )
        
        # Create gap analysis layer
        if 'gap_category' in self.census_wgs84.columns:
            self.gap_layer = self.census_wgs84.hvplot(
                geo=True,
                color='gap_category',
                colormap={
                    'Low Priority': '#fee5d9',
                    'Medium Priority': '#fcae91',
                    'High Priority': '#fb6a4a',
                    'Critical Priority': '#cb181d'
                },
                alpha=0.7,
                hover_cols=['gap_category', 'gap_score', 'total_pop', 'median_income', 'poverty_rate'],
                xlim=self.x_range,
                ylim=self.y_range,
                project=False,
                line_color='black',
                line_width=0.5,
                legend=False
            ).opts(
                title='Priority Levels',
                show_frame=False,
                tools=['hover']
            )
        else:
            # Create placeholder if gap analysis not available
            self.gap_layer = hv.Polygons([]).opts(
                frame_height=650,
                frame_width=1000,
                xlim=self.x_range,
                ylim=self.y_range,
            )
        
        # Create coverage layer (buffered stations)
        if self.radius_miles and hasattr(self, 'stations') and not self.stations.empty:
            try:
                stations_buffered = self.stations.to_crs("EPSG:2272").buffer(self.radius_miles * 1609.34)
                if not stations_buffered.empty:
                    coverage = gpd.GeoDataFrame(geometry=[stations_buffered.union_all()], crs="EPSG:2272")
                    coverage_wgs84 = coverage.to_crs("EPSG:4326")
                    
                    self.coverage_layer = coverage_wgs84.hvplot(
                        geo=True,
                        alpha=0.3,
                        color='blue',
                        line_color='blue',
                        line_width=1,
                        hover=False,
                        xlim=self.x_range,
                        ylim=self.y_range,
                        project=False,
                        legend=False
                    )
                else:
                    self.coverage_layer = None
            except Exception as e:
                print(f"Warning: Could not create coverage layer: {e}")
                self.coverage_layer = None
        else:
            self.coverage_layer = None
        
        # Create stations layer
        hover_cols = ['name', 'num_points']
        if 'max_power' in self.stations_wgs84.columns:
            hover_cols.append('max_power')
            
        self.station_layer = self.stations_wgs84.hvplot.points(
            geo=True,
            color='charging_speed',
            size=8,
            hover_cols=hover_cols,
            clabel='Charging Speed',
            colormap={
                'Level 1 (Slow)': '#4A90E2',
                'Level 2 (Medium)': '#F5A623',
                'DC Fast (Rapid)': '#D0021B'
            },
            xlim=self.x_range,
            ylim=self.y_range,
            project=False,
            legend=False
        ).opts(
            title='Charging Stations',
            show_frame=False,
            tools=['hover']
        )

        # When creating the overlay, add specific width and height
        combined_map = (self.gap_layer * self.coverage_layer * self.station_layer).opts(
            width=800,           # Add explicit width
            height=600,          # Add explicit height
            # Other existing options...
        )
        
        return combined_map

    @param.depends('show_base_map', 'show_gap_analysis', 'show_coverage', 'show_stations', 'show_equity_analysis')
    def view(self):
        """Update map based on layer visibility"""
        layers = []
        
        if self.show_base_map:
            layers.append(self.base_map)
        
        if self.show_gap_analysis:
            layers.append(self.gap_layer)
        
        if self.show_coverage and hasattr(self, 'coverage_layer') and self.coverage_layer is not None:
            layers.append(self.coverage_layer)
        
        if self.show_stations:
            layers.append(self.station_layer)
        
        if not layers:
            return hv.Points([]).opts(
                frame_height=650,
                frame_width=1000,
                xlim=self.x_range,
                ylim=self.y_range,
                title='EV Charging Station Distribution'
            )
        
        # Combine map layers
        map_result = layers[0]
        for layer in layers[1:]:
            map_result = map_result * layer
        
        map_view = map_result.opts(
            toolbar='above',
            tools=['pan', 'wheel_zoom', 'reset', 'hover'],
            active_tools=['wheel_zoom']
        )
        
        # Add equity analysis panel if enabled
        if self.show_equity_analysis and hasattr(self, 'equity_panel'):
            return pn.Row(
                map_view,
                self.equity_panel,
                sizing_mode='stretch_width'
            )
        else:
            return map_view

def update_dashboard(charging_speed='All', service_area_radius=0.5, min_charging_points=1):
    # Filter stations and calculate stats
    filtered_stations = filter_stations(charging_speed, min_charging_points)
    basic_stats = calculate_statistics(filtered_stations)
    coverage_stats = create_coverage_analysis(filtered_stations, service_area_radius)
    
    # Create a simplified map
    census_plot = census_gdf.to_crs("EPSG:4326").hvplot(
        geo=True, 
        color='gap_category',
        colormap={
            'Low Priority': '#fee5d9',
            'Medium Priority': '#fcae91', 
            'High Priority': '#fb6a4a',
            'Critical Priority': '#cb181d'
        },
        tiles='CartoLight',
        line_color='black',
        line_width=0.5,
        alpha=0.7,
        width=800,
        height=600,
        title="Philadelphia EV Charging Gap Analysis",
        legend=False,  # Turn off legend
    ).opts(
        show_grid=False,
        xaxis=None,
        yaxis=None
    )
    
    # Add stations to the map
    stations_plot = filtered_stations.to_crs("EPSG:4326").hvplot.points(
        geo=True,
        color='charging_speed',
        colormap={
            'Level 1 (Slow)': '#4A90E2',
            'Level 2 (Medium)': '#F5A623',
            'DC Fast (Rapid)': '#D0021B'
        },
        size=80,
        alpha=0.8,
        legend=False
    )
    
    # Combine plots
    map_view = census_plot * stations_plot
    map_view = map_view.opts(
        xaxis=None,
        yaxis=None,
        show_grid=False
    )
    
    # Create a custom legend panel
    priority_legend = pn.pane.HTML("""
        <div style="padding: 10px; background-color: white; border: 1px solid #ddd;">
            <h3 style="margin-top: 0;">Priority Levels</h3>
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <div style="width: 20px; height: 20px; background-color: #cb181d; margin-right: 10px;"></div>
                <div>Critical Priority</div>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <div style="width: 20px; height: 20px; background-color: #fb6a4a; margin-right: 10px;"></div>
                <div>High Priority</div>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <div style="width: 20px; height: 20px; background-color: #fcae91; margin-right: 10px;"></div>
                <div>Medium Priority</div>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <div style="width: 20px; height: 20px; background-color: #fee5d9; margin-right: 10px;"></div>
                <div>Low Priority</div>
            </div>
        </div>
    """, width=200)
    
    station_legend = pn.pane.HTML("""
        <div style="padding: 10px; background-color: white; border: 1px solid #ddd; margin-top: 10px;">
            <h3 style="margin-top: 0;">Charging Stations</h3>
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <div style="width: 20px; height: 20px; background-color: #D0021B; border-radius: 10px; margin-right: 10px;"></div>
                <div>DC Fast</div>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <div style="width: 20px; height: 20px; background-color: #F5A623; border-radius: 10px; margin-right: 10px;"></div>
                <div>Level 2</div>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <div style="width: 20px; height: 20px; background-color: #4A90E2; border-radius: 10px; margin-right: 10px;"></div>
                <div>Level 1</div>
            </div>
        </div>
    """, width=200)
    
    # Return the complete dashboard
    return pn.Column(
        pn.Row(
            # Left column with controls
            pn.Column(
                pn.pane.Markdown("## Filter Options"),
                charging_speed_filter,
                coverage_radius,
                min_points,
                pn.pane.Markdown("## Legend"),
                priority_legend,
                station_legend,
                width=250
            ),
            # Right column with map and stats
            pn.Column(
                pn.pane.HoloViews(map_view),
                pn.Row(
                    pn.Column(pn.pane.Markdown("### Station Statistics"), 
                              pn.pane.DataFrame(pd.DataFrame([basic_stats]).T.rename(columns={0: 'Value'}))),
                    pn.Column(pn.pane.Markdown("### Coverage Analysis"), 
                              pn.pane.DataFrame(pd.DataFrame([coverage_stats]).T.rename(columns={0: 'Value'})))
                )
            )
        )
    )

# Initialize Panel extension
pn.extension('tabulator', sizing_mode="stretch_width", loading_spinner='dots', loading_color='#00aa41')

# Use bind to create a reactive dashboard
reactive_dashboard = pn.bind(update_dashboard, 
    charging_speed=charging_speed_filter, 
    service_area_radius=coverage_radius, 
    min_charging_points=min_points)

# Create the panel app with the reactive components
dashboard = pn.Column(
    pn.pane.Markdown("# Philadelphia EV Charging Gap Analysis"),
    reactive_dashboard,
    sizing_mode='stretch_width'
)

# Create a self-contained dashboard HTML file with everything embedded
dashboard.save("analysis/dashboard.html", embed=True, embed_json=True, resources='inline')

# Simplified folium map creation
try:
    # Create a basic folium map with census tracts and stations
    m = folium.Map(location=[39.9526, -75.1652], zoom_start=11, tiles='CartoDB positron')
    
    # Add a simplified legend
    legend_html = '''
    <div style="position: fixed; bottom: 50px; right: 50px; z-index:9999; background-color:white; padding:10px; border:2px solid grey;">
    <p><b>Priority Levels</b></p>
    <p><i style="background:#fee5d9; padding:5px;">&nbsp;&nbsp;&nbsp;</i> Low Priority</p>
    <p><i style="background:#fcae91; padding:5px;">&nbsp;&nbsp;&nbsp;</i> Medium Priority</p>
    <p><i style="background:#fb6a4a; padding:5px;">&nbsp;&nbsp;&nbsp;</i> High Priority</p>
    <p><i style="background:#cb181d; padding:5px;">&nbsp;&nbsp;&nbsp;</i> Critical Priority</p>
    <p><i style="background:white; border:1px solid black; padding:5px;">&nbsp;&nbsp;&nbsp;</i> EV Station</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Save and display map
    m.save('analysis/priority_map.html')
    print("Successfully created priority map")
except Exception as e:
    print(f"Error creating folium map: {e}") 