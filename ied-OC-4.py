import pandas
import streamlit as st
from PIL import Image
import piexif
from fractions import Fraction
import pandas as pd
import pydeck as pdk
import tempfile
import os
import requests


# =====================  Functions to prompt values from exif data ================================
def prompt_str(value: bytes) -> str:
    return value.decode()


def prompt_coord(value: tuple) -> str:
    """
    function to convert GPS coord value from data exif format to decimal
    :param value: exif value
    :return: text of decimal conversion
    """
    dec = int(value[0][0] / value[0][1])
    dec += int(value[1][0] / value[1][1]) / 60
    dec += value[2][0] / (value[2][1] * 3600)
    return str(dec)


# ====================== other utility functions    ==============================================
def modify_value(inputs: dict, image: Image, data: dict) -> None:
    """
    function to modify exif and save a new picture with new exif
    :param inputs: dict of st.input_text values (keys are tag_name)
    :param image:  processed image
    :param data: exif data
    :return: None
    """
    # loop through tags :
    for tag in inputs.keys():
        value = inputs[tag]
        # ignore empty input_texts
        if value == "":
            continue
        # test input value and format value to be prompted
        test_value, value = get_value_format(tag, value)
        if not test_value:
            # pop up to explain error
            st.error(f"La valeur pour {tag} n'est pas au bon format")
            continue
        # get current ifd :
        ifd = "0th" if tag in exif_trad["0th"].keys() else "GPS"
        # change value in data
        data[ifd][exif_trad[ifd][tag][1]] = value

    # create a new Image
    new_image = image.copy()
    # convert data into bytes
    exif_bytes = piexif.dump(data)
    # save copy to img_copy.jpg in temp directory
    new_image_path = os.path.join(tempfile.gettempdir(), "img_copy.jpg")
    new_image.save(new_image_path, "jpeg")
    # insert exif in bytes format into created image
    piexif.insert(exif_bytes, new_image_path)


def get_value_format(tag: str, value) -> tuple:
    """
    function to test if a text fits format data
    :param tag: exif tag name
    :param value: input value
    :return: tuple : boolean to test if value fits format data, and value to be inserted into data dict
    """
    test = False
    new_value = None
    if tag in ["ImageWidth", "ImageLength"]:
        try:
            new_value = int(value)
            test = True
        except TypeError:
            return False, value
    elif tag in ["Make", "Model"]:
        new_value = value
        test = True
    elif tag == "DateTime":
        try:
            date = value.split()
            formated_date = [data.split(":") for data in date]
            for i in range(2):
                for j in range(3):
                    int(formated_date[i][j])
            new_value = value.encode()
            test = True
        except (IndexError, TypeError):
            return False, new_value
    elif tag in ["GPSLatitude", "GPSLongitude"]:
        try:
            # test
            value = float(value)
            # data processing
            abs_value = abs(value)
            deg = int(abs_value)
            t1 = (abs_value - deg) * 60
            min = int(t1)
            sec = round((t1 - min) * 60, 5)
            new_value = (to_fraction(deg), to_fraction(min), to_fraction(sec))
            test = True
        except TypeError:
            return False, value
    elif tag == "GPSLatitudeRef":
        test = value in ["N", "S"]
        new_value = value.encode()
    elif tag == "GPSLongitudeRef":
        test = value in ["E", "W"]
        new_value = value.encode()
    return test, new_value


def to_fraction(value: float) -> tuple:
    """
    function to convert float value into tuple with numerator and denominator
    :param value: float value
    :return: (numerator, denominator)
    """
    f = Fraction(str(value))
    return f.numerator, f.denominator


# translation dict : {tag_name: (translation , tag_code, callable to print value)
exif_trad = {"0th":
                 {"ImageWidth": ("largeur en pixels", piexif.ImageIFD.ImageWidth, None),
                  "ImageLength": ("largeur en pixels", piexif.ImageIFD.ImageLength, None),
                  "Make": ("marque de l'appareil utilisé", piexif.ImageIFD.Make, prompt_str),
                  "Model": ("modèle de l'appareil utilisé", piexif.ImageIFD.Model, prompt_str),
                  "DateTime": ("Date de prise de vue", piexif.ImageIFD.DateTime, prompt_str)},
             "GPS":
                 {"GPSLatitudeRef": ("direction latitude", piexif.GPSIFD.GPSLatitudeRef, prompt_str),
                  "GPSLatitude": ("latitude", piexif.GPSIFD.GPSLatitude, prompt_coord),
                  "GPSLongitudeRef": ("direction longitude", piexif.GPSIFD.GPSLongitudeRef, prompt_str),
                  "GPSLongitude": ("longitude", piexif.GPSIFD.GPSLongitude, prompt_coord)}
             }


def get_lat(data: dict) -> float:
    """
    function to convert latitude from (deg, min, sec) format to decimal
    :param data: exif data dict
    :return: decimal value of latitude
    """
    if piexif.GPSIFD.GPSLatitude not in data['GPS'].keys():
        return 0
    lat_frac = data['GPS'][piexif.GPSIFD.GPSLatitude]
    lat_dec = float(prompt_coord(lat_frac))
    if data['GPS'][piexif.GPSIFD.GPSLatitudeRef] == b"S":
        lat_dec = - lat_dec
    return lat_dec


def get_long(data: dict) -> float:
    """
    function to convert longitude from (deg, min, sec) format to decimal
    :param data: exif data dict
    :return: decimal value of longitude
    """
    if piexif.GPSIFD.GPSLongitude not in data['GPS'].keys():
        return 0
    long_frac = data['GPS'][piexif.GPSIFD.GPSLongitude]
    long_dec = float(prompt_coord(long_frac))
    if data['GPS'][piexif.GPSIFD.GPSLongitudeRef] == b"W":
        long_dec = - long_dec
    return long_dec


def main():
    st.title("Application stremlit test")

    menu = ["EXIF", "Lieux"]
    choice = st.sidebar.selectbox("Menu", menu)
    #   ==================      EXIF part   ===========================
    if choice == "EXIF":
        st.subheader("Modify EXIF")
        st.text("Chargez une photo et modifiez-en les métadonnées")
        uploaded_image = st.file_uploader("Sélectionnez une photo", ["jpg", "png"])
        my_image: Image
        # providing default path
        default_pic_path = os.path.join(tempfile.gettempdir(), "chien.jpg")
        if not uploaded_image:
            try:
                file = open(default_pic_path, "r")
                file.close()
            except FileNotFoundError:
                url = "https://raw.githubusercontent.com/PierreIED/streamlit_projects/master/chien.jpg"
                r = requests.get(url)
                file = open(default_pic_path, "wb")
                file.write(r.content)
                file.close()
            my_image = Image.open(default_pic_path)
        else:
            my_image = Image.open(uploaded_image)

        data = piexif.load(my_image.info['exif'])

        col1, col2 = st.columns(2)

        with col1:
            st.image(my_image)
            latitude = get_lat(data)
            longitude = get_long(data)
            df = pandas.DataFrame({
                'lat': [latitude],
                'lon': [longitude]
            })
            st.map(df, zoom=6)
        with col2:
            st.info("Métadonnées EXIF")

            inputs = {}

            for ifd in exif_trad.keys():
                for tag_name in exif_trad[ifd].keys():
                    tag_code = exif_trad[ifd][tag_name][1]
                    text_value = ""
                    if tag_code in data[ifd].keys():
                        value = data[ifd][tag_code]
                        text_value = exif_trad[ifd][tag_name][2](value) if exif_trad[ifd][tag_name][2] else value
                    inputs[tag_name] = st.text_input(f"{exif_trad[ifd][tag_name][0]}",
                                                     value=text_value)
            st.button("changer les données", on_click=modify_value, args=(inputs, my_image, data))

    # ====================      Location part   =======================
    else:
        data_pandas = {
            'city': ["SaintAndré 13 Voies", "Rennes", "Mulhouse", "Greffern", "Strasbourg", "Argenteuil", "La Glacerie",
                     "Lieusaint"],
            'years': [17, 2, 4, 1, 1, 2, 2, 10],
            'lat': [46.92294231382949,
                    48.11833569032241,
                    47.73846972769271,
                    48.74947715163981,
                    48.59005804751027,
                    48.92860234577915,
                    49.6190165971145,
                    49.48219891080739],
            'lon': [-1.412453434220721,
                    -1.6328255244334595,
                    7.319256116526316,
                    8.00728074558261,
                    7.743737616762319,
                    2.2252031323280907,
                    -1.6307539550132186,
                    -1.462997874384719]}
        df = pd.DataFrame.from_dict(data_pandas)

        data_pandas2 = {'distance': [163, 845, 150, 150, 114, 114, 497, 348, 21],
                        'lat': [46.92294231382949,
                                48.11833569032241,
                                47.73846972769271,
                                48.74947715163981,
                                47.73846972769271,
                                48.59005804751027,
                                47.73846972769271,
                                48.92860234577915,
                                49.6190165971145, ],
                        'lon': [-1.412453434220721,
                                -1.6328255244334595,
                                7.319256116526316,
                                8.00728074558261,
                                7.319256116526316,
                                7.743737616762319,
                                7.319256116526316,
                                2.2252031323280907,
                                -1.6307539550132186],
                        'lat2': [48.11833569032241,
                                 47.73846972769271,
                                 48.74947715163981,
                                 47.73846972769271,
                                 48.59005804751027,
                                 47.73846972769271,
                                 48.92860234577915,
                                 49.6190165971145,
                                 49.48219891080739],
                        'lon2': [-1.6328255244334595,
                                 7.319256116526316,
                                 8.00728074558261,
                                 7.319256116526316,
                                 7.743737616762319,
                                 7.319256116526316,
                                 2.2252031323280907,
                                 -1.6307539550132186,
                                 -1.462997874384719]
                        }

        df2 = pd.DataFrame.from_dict(data_pandas2)

        all_layers = {
            "Années passées": pdk.Layer(

                "ScatterplotLayer",
                data=df,
                get_position=["lon", "lat"],
                get_color=[200, 30, 0, 160],
                get_radius="[years]",
                radius_scale=8000,

            ),
            "noms des villes": pdk.Layer(
                "TextLayer",
                data=df,
                get_position=["lon", "lat"],
                get_text="city",
                get_color=[0, 0, 0, 200],
                get_size=15,
                get_alignment_baseline="'bottom'",
            ),
            "Déménagements": pdk.Layer(
                "ArcLayer",
                data=df2,
                get_source_position=["lon", "lat"],
                get_target_position=["lon2", "lat2"],
                get_source_color=[200, 30, 0, 160],
                get_target_color=[200, 30, 0, 160],
                auto_highlight=True,
                width_scale=0.0001,
                get_width="outbound",
                width_min_pixels=3,
                width_max_pixels=30,
            )

        }

        col3, col4 = st.columns(2)
        with col3:
            selected_layers = [
                layer
                for layer_name, layer in all_layers.items()
                if st.checkbox(layer_name, True)
            ]

        with col4:
            st.subheader("Lieux d'habitation")
            st.text("Voici la liste des lieux que j'ai habités, ainsi que les trajets des déménagements.")
            if selected_layers:
                st.pydeck_chart(
                    pdk.Deck(
                        map_style=None,
                        initial_view_state={
                            "latitude": 46.89,
                            "longitude": 2.53,
                            "zoom": 5,
                            "pitch": 50,
                        },
                        layers=selected_layers,
                    )
                )
            else:
                st.error("Please choose at least one layer above.")

    return "hello world"


if __name__ == '__main__':
    main()
