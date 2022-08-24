import pandas
import streamlit as st
from PIL import Image
import piexif
from fractions import Fraction


def prompt_str(value: bytes) -> str:
    return value.decode()


def prompt_coord(value: tuple) -> str:
    dec = int(value[0][0] / value[0][1])
    dec += int(value[1][0] / value[1][1]) / 60
    dec += value[2][0] / (value[2][1] * 3600)
    return str(dec)


def modify_value2(inputs: dict, image: Image, data: dict):
    for tag in inputs.keys():
        value = inputs[tag]
        if value == "":
            continue
        test_value, value = get_value_format(tag, value)
        if not test_value:
            st.error(f"La valeur pour {tag} n'est pas au bon format")
            continue

        ifd = "0th" if tag in exif_trad["0th"].keys() else "GPS"
        data[ifd][exif_trad[ifd][tag][1]] = value
    new_image = image.copy()

    exif_bytes = piexif.dump(data)
    new_image.save("img_copy.jpg", "jpeg")

    piexif.insert(exif_bytes, "img_copy.jpg")


def get_value_format(tag: str, value) -> tuple:
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
    f = Fraction(str(value))
    return f.numerator, f.denominator


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
    if piexif.GPSIFD.GPSLatitude not in data['GPS'].keys():
        return 0
    lat_frac = data['GPS'][piexif.GPSIFD.GPSLatitude]
    lat_dec = float(prompt_coord(lat_frac))
    if data['GPS'][piexif.GPSIFD.GPSLatitudeRef] == b"S":
        lat_dec = - lat_dec
    return lat_dec


def get_long(data: dict) -> float:
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
        # providing default path

        my_image = Image.open("chien.jpg") if not uploaded_image else Image.open(uploaded_image)
        data = piexif.load(my_image.info['exif'])

        col1, col2 = st.columns(2)

        with col1:
            st.image(my_image)
            latitude = get_lat(data)
            longitude = get_long(data)
            df = pandas.DataFrame({
                'awesome cities': ['Chicago'],
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
            st.button("changer les données", on_click=modify_value2, args=(inputs, my_image, data))

    # ====================      Location part   =======================
    else:
        pass
    return "hello world"


if __name__ == '__main__':
    main()
