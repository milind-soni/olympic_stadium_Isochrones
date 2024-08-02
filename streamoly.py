import streamlit as st
import pydeck as pdk
import pandas as pd
import requests
import numpy as np
from io import StringIO

# Fused API endpoints
FUSED_API_URL = "https://www.fused.io/server/v1/realtime-shared/ee28781f18bbb5369441e13c90a3e2ca7af582f266fdfd9edc4c56ca05321830/run/file"

# Path to your CSV file
CSV_PATH = "olympicsst/2024_paris_iso.csv"


def load_stadium_data():
    df = pd.read_csv(CSV_PATH)
    return df


def fetch_data(stadium_codes, travel_time, travel_mode, resolution=11):
    params = {
        "dtype_out_raster": "png",
        "dtype_out_vector": "csv",
        "travel_time": travel_time,
        "travel_mode": travel_mode,
        "resolution": resolution,
    }
    # Add stadium codes as separate parameters
    for i, code in enumerate(stadium_codes):
        params[f"stadium_codes[{i}]"] = code

    response = requests.get(FUSED_API_URL, params=params)
    response.raise_for_status()
    content = response.text.strip()
    if not content:
        raise ValueError("Empty response received from the API")
    try:
        return pd.read_csv(StringIO(content))
    except pd.errors.EmptyDataError:
        st.error(f"Empty or invalid CSV data received. Raw content: {content[:1000]}")
        raise ValueError("Empty or invalid CSV data received from the API")


def fetch_airbnb_data(city="Paris"):
    params = {"dtype_out_raster": "png", "dtype_out_vector": "csv", "city": city}
    response = requests.get(AIRBNB_API_URL, params=params)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text))


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def main():
    st.title("Paris 2024 : Stadiums, Stays & City Access")

    # Load stadium data
    stadium_data = load_stadium_data()
    stadium_names = stadium_data["Nom_Site"].tolist()
    name_to_code = dict(zip(stadium_data["Nom_Site"], stadium_data["Code_Site"]))

    # Sidebar for user inputs
    st.sidebar.header("Parameters")
    selected_stadiums = st.sidebar.multiselect(
        "Select Stadiums",
        options=stadium_names,
        default=[stadium_names[0]] if stadium_names else [],
    )
    travel_time = st.sidebar.slider("Travel Time (minutes)", 1, 60, 5)
    travel_mode = st.sidebar.selectbox("Travel Mode", ["auto", "pedestrian", "bike"])

    # Convert selected stadium names to codes
    selected_stadium_codes = [name_to_code[name] for name in selected_stadiums]

    # Display selected stadium information
    if selected_stadiums:
        st.subheader("Selected Stadiums")
        selected_data = stadium_data[stadium_data["Nom_Site"].isin(selected_stadiums)]

    # Fetch data
    if st.sidebar.button("Update Visualization"):
        with st.spinner("Fetching data..."):
            try:
                st.write(
                    f"Fetching data for stadium codes: {', '.join(selected_stadium_codes)}"
                )
                data = fetch_data(selected_stadium_codes, travel_time, travel_mode)

                # Process data for visualization
                data["cell_id"] = data["cell_id"].astype(str)
                data["cnt"] = data["cnt"].astype(float)
                max_cnt = data["cnt"].max()

                def get_elevation_and_color(row):
                    elevation = row["cnt"]
                    color_intensity = 1 - (row["cnt"] / max_cnt)
                    return elevation, [255, int(color_intensity * 255), 0]

                data["elevation"], data["color"] = zip(
                    *data.apply(get_elevation_and_color, axis=1)
                )

                # Create hexagon layer
                layer = pdk.Layer(
                    "H3HexagonLayer",
                    data,
                    pickable=True,
                    stroked=True,
                    filled=True,
                    extruded=True,
                    get_hexagon="cell_id",
                    get_fill_color="color",
                    get_elevation="elevation",
                    elevation_scale=20,
                )

                # Create scatter layer for stadium locations
                scatter_data = stadium_data[
                    stadium_data["Nom_Site"].isin(selected_stadiums)
                ]
                scatter_layer = pdk.Layer(
                    "ScatterplotLayer",
                    scatter_data,
                    get_position=["longitude", "latitude"],
                    get_color=[200, 30, 0, 160],
                    get_radius=200,
                    pickable=True,
                )

                # Set the initial view state
                view_state = pdk.ViewState(
                    latitude=scatter_data["latitude"].mean(),
                    longitude=scatter_data["longitude"].mean(),
                    zoom=11,
                    pitch=20,
                )

                # Render the map
                st.pydeck_chart(
                    pdk.Deck(
                        layers=[layer, scatter_layer],
                        initial_view_state=view_state,
                        tooltip={"text": "{stadium_name}\nCount: {cnt}"},
                    )
                )

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.write(
                    "Please try again with different parameters or contact support if the issue persists."
                )


if __name__ == "__main__":
    main()
