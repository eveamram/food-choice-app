import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd

import requests
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image
from datetime import datetime
import lxml

from email.message import EmailMessage
import ssl
import smtplib

from app_functions import calculate_total_emission_individual, convert_units, baseline_cutoff, evaluate_recipe, find_eligible_category, find_closest_alternative, compare_to_vehicle
from email_sender import email_sender, email_password

st.set_page_config(
    page_title="Alternative Recipe",
    page_icon="image/vegetable.png",
    layout="wide"
)

df = pd.read_csv("cleaned_data/ingredients2.csv")
nutrient_df = pd.read_csv("cleaned_data/nutrient_df.csv")
unit_df = pd.read_csv("cleaned_data/unit_conversion.csv")
footprints_df = pd.read_csv("cleaned_data/carbon_footprints.csv")

st.markdown("<h1 style='text-align: center;'>Alternative Recipe</h1>", unsafe_allow_html=True)

image_columns = st.columns(3)
with image_columns[0]:
    st.write("")
with image_columns[1]:
    vegetable_image = Image.open("image/vegetable.png")
    st.image(vegetable_image, width=250)
with image_columns[2]:
    st.write("")

user_df = pd.DataFrame(columns=["Category:", "Ingredient:", "Amount:", "Unit:", "CO2 Emission (Kg):"])

if "df" not in st.session_state:
    st.session_state.df = user_df

if "eval_button" not in st.session_state:
    st.session_state["eval_button"] = False

# if "all_total_emssion" not in st.session_state:
#     st.session_state["all_total_emission"] = 0

def google_search_image(query):
    url = 'https://www.google.com/search?q={0}&tbm=isch'.format(query)
    content = requests.get(url).content
    soup = BeautifulSoup(content, 'lxml' )
    images = soup.findAll('img')

    all_image_list = []

    for image in images:
        all_image_list.append(image.get('src'))

    return all_image_list[1]

placeholder = st.empty()

with st.expander("➕ Click to Add Ingredient"):
    # if "is_expanded" not in st.session_state:
    #     st.session_state["is_expanded"] = False

    ingredient_columns = st.columns([2,3,1,1])

    with ingredient_columns[0]:
        st.session_state["is_expanded"] = True
        selected_category = st.selectbox(
                "Category:", df["FoodGroupName"].unique(), key="input_col1")
    with ingredient_columns[1]:
        df_ingredient = df[df["FoodGroupName"] == st.session_state.input_col1]
        selected_ingredient = st.selectbox(
            "Ingredient:", df_ingredient["FoodDescription"].unique(), key="input_col2")
    with ingredient_columns[2]:
        selected_amount = st.number_input("Amount: ", key="input_col3", step=1, min_value=0)
        if type(selected_amount) == str:
            st.error("Please enter a numeric value.")
    with ingredient_columns[3]:
        selected_unit = st.selectbox(
            "Unit:", unit_df["from_unit"].unique(), key="input_col4"
        )

    nutrition_tab, metrics_tab = st.tabs(["Nutritional Information", "Summary Metrics"])
    with nutrition_tab:
        st.subheader(f"{selected_ingredient}")
        nutrient_df_selected = nutrient_df[nutrient_df["FoodDescription"] == selected_ingredient].iloc[:, 3:15]

        st.image(google_search_image(selected_ingredient), width=200)

        columns = ["Alcohol", "Caffeine", "Calcium", "Carbohydrate", "Cholesterol", "Copper", "Fats",
                   "Fatty Acids (Polysaturated)", "Fatty Acids (Unsaturated)", "Fibre", "Iron", "Lactose"]

        nutrient_df_selected.columns = columns
        st.write(f"Nutrition Information for 100g of {selected_ingredient}, retrieved from [Statistics Canada](https://www.canada.ca/en/health-canada/services/food-nutrition/healthy-eating/nutrient-data/canadian-nutrient-file-2015-download-files.html).")
        st.table(nutrient_df_selected)

    with metrics_tab:
        st.subheader(f"{selected_ingredient}")
        selected_amount = float(selected_amount)
        try:
            total_emission = calculate_total_emission_individual(selected_ingredient, selected_amount, selected_unit)
            st.session_state["total_emission"] = (total_emission / 1000)
            total_amount = convert_units(selected_amount, selected_unit)
        except:
            total_emission = 0

        tab2_col1, tab2_col2 = st.columns(2)

        with tab2_col1:
            st.metric(label="Total Amount of Food in Kg", value=(total_amount / 1000))
        with tab2_col2:
            st.metric(label="Total CO2 Emission in Kg", value=(total_emission / 1000))

    submit = st.button("Add Ingredient", key="submit_button")

    if submit:
        st.session_state.df.loc[len(st.session_state.df)] = [selected_category, selected_ingredient, selected_amount,
                                                             selected_unit, (total_emission / 1000)]

if "reset" not in st.session_state:
    st.session_state["reset"] = False
    st.session_state["is_expanded"] = True

def reset_df():
    turn_reset_on()
    st.session_state["finalize_recipe"] = False
    if st.session_state["reset"] == True:
        st.session_state.df = pd.DataFrame(columns=["Category:", "Ingredient:", "Amount:", "Unit:", "CO2 Emission (Kg):"])
        st.success("Your recipe has been updated.", icon="✅")
        st.session_state["reset"] = False

def turn_reset_on():
    st.session_state["reset"] = True

if len(st.session_state.df) > 0:
    st.header("Your Recipe:")
    if st.session_state["reset"] != True:
        st.experimental_data_editor(st.session_state.df, use_container_width=True)

empty_col, button_col, reset_col, empty_col2 = st.columns([3,3,3,3])
with empty_col:
    st.write("")
with button_col:
    evaluate_submit = st.button("Evaluate My Recipe!", use_container_width=True)
with reset_col:
    reset_button = st.button("Reset My Recipe!", use_container_width=True, on_click=reset_df)

with empty_col2:
    st.write("")

def display_alternative():
    st.session_state["eval_button"] = True

if evaluate_submit:
    st.divider()
    st.header("See My Results:")
    results_tab_col1, results_tab_col2 = st.columns([3,4])
    with results_tab_col1:
        total_emission_recipe, label = evaluate_recipe(st.session_state.df)
        st.session_state["all_total_emission"] = total_emission_recipe
        delta_value = baseline_cutoff - total_emission_recipe
        delta_value = round(delta_value, 3)
        st.metric(label="Total CO2 Emission Generated in Manufactoring Your Recipe:",
                  value=f"{round(total_emission_recipe, 3)} Kg", delta=f"{delta_value} Kg")
        if label == "High Impact":
            red_image = Image.open("image/red_icon.png")
            st.image(red_image, width=150)
        elif label == "Medium Impact":
            yellow_image = Image.open("image/orange_icon.png")
            st.image(yellow_image, width=150)
        elif label == "Low Impact":
            green_image = Image.open("image/green_icon.png")
            st.image(green_image, width=150)
    with results_tab_col2:
        st.subheader("Evaluation Results:")
        with st.expander("❕View Label Assessment Metrics"):
            st.write("Label cut-off values are retrieved from [Statistics Canada](https://www150.statcan.gc.ca/n1/pub/16-508-x/16-508-x2019004-eng.html)."
                     " Total greenhouse gas emission value from household food and beverages products & services (from 2015) is divided by the number of total households in Canada, assuming that on average there are 3 members in a household.")
            st.markdown("- :red[High Impact] : Assigned if the total CO2 emission produced from recipe > cut-off value")
            st.markdown("- :orange[Medium Impact] : Assigned if the total CO2 emission produced from recipe is in between hjgh and low impact")
            st.markdown("- :green[Low Impact] : Assigned if the total CO2 emission produced from recipe < (cut-off value * 0.5)")

        if label == "High Impact":
            st.markdown(f"<h3 style='color:red'>{label}</h3>", unsafe_allow_html=True)
            st.write(
                f"Total CO2 emission generated from your recipe is {abs(delta_value)} Kg higher than the cut-off value, resulting in high impact on CO2 emissions. Alternative recipe is strongly suggested.")
            eval_button = st.button("Suggest Alternative Recipe", on_click=display_alternative)
        elif label == "Medium Impact":
            st.markdown(f"<h3 style='color:orange'>{label}</h3>", unsafe_allow_html=True)
            st.write(
                f"Total CO2 emission generated from your recipe is {abs(delta_value)} Kg higher than the cut-off value, resulting in intermediate impact on CO2 emissions. . Alternative recipe is advised.")
            eval_button = st.button("Suggest Alternative Recipe", on_click=display_alternative)
        elif label == "Low Impact":
            st.markdown(f"<h3 style='color:green'>{label}</h3>", unsafe_allow_html=True)
            st.write(f"Total CO2 emission generated from your recipe is {delta_value} Kg lower than the cut-off value, not significantly impacting the CO2 emissions. No alternative recipe is needed.")

if "finalize_recipe" not in st.session_state:
    st.session_state["finalize_recipe"] = False

def turn_swap_category_on():
    if "swap_category" not in st.session_state:
        st.session_state["swap_category"] = True
    st.session_state["eval_button"] = True
    st.session_state["swap_category"] = swap_category

def find_alternative(food, category, num_try=0):
    replacement_ingredient = find_closest_alternative(df, footprints_df, category, food, num_try)
    st.markdown(f"<h3 style='color:green'>{replacement_ingredient}</h3>", unsafe_allow_html=True)
    st.write(f"{replacement_ingredient} is the closest alternative to your chosen ingredient.")
    return replacement_ingredient

def another_suggestion(food, category, num_try):
    find_alternative(food, category, num_try)

if "display_updated_message" not in st.session_state:
    st.session_state["display_updated_message"] = False

def turn_on_eval_button():
    st.session_state["swap_category"] = True

def change_dataframe():
    st.session_state["eval_button"] = True
    current_amount = st.session_state.df[st.session_state.df["Ingredient:"] == st.session_state.ingredient]["Amount:"].values[0]
    for ind, row in st.session_state.df.iterrows():
        if row["Ingredient:"] == st.session_state.ingredient:
            st.session_state.df.loc[ind, "Ingredient:"] = selected_ingredient_swap
            st.session_state.df.loc[ind, "Amount:"] = current_amount
            st.session_state.df.loc[ind, "Category:"] = swap_category
            st.session_state.df.loc[ind, "CO2 Emission (Kg):"] = (calculate_total_emission_individual(selected_ingredient_swap, current_amount, "g") / 1000)

def finalize_recipe():
    st.session_state["eval_button"] = True
    st.session_state["finalize_recipe"] = True

if "success_message" not in st.session_state:
    st.session_state["success_message"] = False

if "alternative_number" not in st.session_state:
    st.session_state["alternative_number"] = 0

def increment_alternative_number():
    st.session_state.alternative_number += 1

def send_email():
    current_time = datetime.now()
    subject = f"Your Alternative Recipe Generated on {current_time}"

    em = EmailMessage()
    em["From"] = email_sender
    em["To"] = email_receiver
    em["Subject"] = subject
    st.write(final_df.to_string())
    em.set_content(final_df.to_string())

    context = ssl.create_default_context()

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
        smtp.login(email_sender, email_password)
        smtp.sendmail(email_sender, email_receiver, em.as_string())

if "hold_on_df" not in st.session_state:
    st.session_state["hold_on_df"] = False


if st.session_state["finalize_recipe"] == True:
    st.divider()
    st.session_state["eval_button"] = False
    final_image_col, final_text_col = st.columns([4,7])
    changed_emission = st.session_state.df["CO2 Emission (Kg):"].sum()
    subtracted_emission = st.session_state.all_total_emission - changed_emission
    compare_to_vehicle_value = compare_to_vehicle(subtracted_emission)
    with final_image_col:
        if changed_emission < st.session_state.all_total_emission:
            success_image = Image.open("image/success.png")
            st.image(success_image, width=350)
        elif changed_emission >= st.session_state.all_total_emission:
            # st.write(st.session_state.all_total_emission)
            warning_image = Image.open("image/warning.png")
            st.image(warning_image, width=200)
    with final_text_col:
        if changed_emission < st.session_state.all_total_emission:
            st.markdown("<h3 style='color:green'>Success!</h3>", unsafe_allow_html=True)
            text_col0, image_col0, text_col1 = st.columns([3,1,5])
            with text_col0:
                st.metric("Total CO2 Kg produced:", changed_emission, subtracted_emission)
            with image_col0:
                truck_image = Image.open("image/truck.png")
                st.image(truck_image, width=70)
            with text_col1:
                st.markdown(f"<h6>How much is {'{:.3f}'.format(subtracted_emission)} kg of CO2 emission?</h6>", unsafe_allow_html=True)
                st.write(f"This is equal to CO2 emission produced from {'{:.3f}'.format(compare_to_vehicle_value)} miles of vehicle ride.")
            st.write(f'Total {"{:.3f}".format(subtracted_emission)} Kg of CO2 equivalent has been reduced compared to your original recipe!')
            email_receiver = st.text_input("Your email address:")
            final_df = st.session_state.df
            st.button("\nSend Email", key="send_email", on_click=send_email)
            st.write("Make sure to press Enter before you click on Send Email button.")
        elif changed_emission >= st.session_state.total_emission:
            st.session_state["hold_on_df"] = True
            st.markdown("<h3 style='color:blue'>Hold On...</h3>", unsafe_allow_html=True)
            st.info(f"You have made changes in your recipe, but it didn't reduce total amount of CO2 produced. Try making altenative selection.", icon="ℹ️")
            if st.session_state["hold_on_df"] == True:
                st.session_state["finalize_recipe"] = True


if st.session_state["eval_button"] == True:
    st.divider()
    col1, col0, col2= st.columns([4,1,8])
    with col1:
        st.subheader("Alternative Recipe:")
        st.markdown("Alternative Recipe suggests an ingredient of :green[lower carbon emission] footprint that has the closest nutritional values with the original ingredient.")
        original_ingredients = st.session_state.df["Ingredient:"].unique()
        original_ingredients_select = st.selectbox("Select Ingredient to Swap:", original_ingredients,
                                                   key="recipe_ingredient", on_change=turn_swap_category_on)
        st.session_state["original_ingredient"] = original_ingredients_select
        st.session_state["ingredient"] = st.session_state.original_ingredient
        eligible_categories = find_eligible_category(df, footprints_df, st.session_state.ingredient)
        st.session_state["category"] = eligible_categories
        try:
            swap_category = st.selectbox("Swap with Ingredient From Category:", st.session_state.category, key="swap_category")
        except:
            swap_category = st.selectbox("Swap with Ingredient From Category:", "",
                                         key="swap_no_category")
    with col0:
        st.write("")
    with col2:
        selected_ingredient_swap = find_alternative(original_ingredients_select, swap_category, st.session_state.alternative_number)
        st.image(google_search_image(selected_ingredient_swap), width=200)
        # selected_nutrient = nutrient_df[nutrient_df["FoodDescription"] == selected_ingredient_swap].iloc[:, 3:15]
        # columns = ["Alcohol", "Caffeine", "Calcium", "Carbohydrate", "Cholesterol", "Copper", "Fats",
        #            "Fatty Acids (Polysaturated)", "Fatty Acids (Unsaturated)", "Fibre", "Iron", "Lactose"]
        # selected_nutrient.columns = columns
        # st.table(selected_nutrient)
        button_col1, image_col, button_col2 = st.columns(3)
        with button_col1:
            save_button = st.button("Save Ingredient", key="save_button", on_click=change_dataframe, use_container_width=True)
            st.session_state["success_message"] = False
            if save_button:
                st.session_state["success_message"] = True
        with image_col:
            st.button("Another Selection", key="another_selection", use_container_width=True, on_click=increment_alternative_number)
        with button_col2:
            finish_button = st.button("Finalize My Recipe!", key="finalize_button", on_click=finalize_recipe, use_container_width=True)









