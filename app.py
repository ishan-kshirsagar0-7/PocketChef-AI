import os
from fastapi import FastAPI, File, UploadFile, Form
from typing import List, Optional
from bing_image_urls import bing_image_urls
import urllib.request
from PIL import Image
from io import BytesIO
import re
import json
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

vision_model = genai.GenerativeModel("gemini-pro-vision")
recipe_model = genai.GenerativeModel("gemini-pro")
thumbnail_model = genai.GenerativeModel("gemini-pro")

ingredients_vision_prompt = """
Given to you is an image of food items or ingredients. Your main mission is to extract the item names, and to display them in
format of a Python list. DO NOT make up fake items, return only those items which you are 100 percent sure of, that are present. Be clear about the item name that you extract, do not be vague. No matter what the cost, ONLY extract items that you are confident are there, otherwise skip them.
"""

recipe_prompt = """
You are the Gordon Ramsey of India. When a list of ingredients is given to you, you are perfectly skilled at hand-picking which items to use,
to cook what dish. You know every single recipe of every single Indian dish, by heart. Hence, when a list of ingredients is given to you,
you precisely recognize what dish can be cooked based on that list. Now, you are given a list of ingredients. Your main mission to provide
a recipe, that is grounded to reality, and caters the taste of Indian audience. DO NOT make up fake recipes, and don't come up with unconventional combinations such as mixing fruit in spicy dishes, or cooking fruits in oil, etc. Create conventional, pre-existing, traditional indian recipes from the list of ingredients. If the ingredients aren't Indian, you are free to create a suitable appropriate recipe using those.

Here are 8 GOLDEN RULES that you MUST adhere to :

1. Your dish MUST use only those ingredients that are provided to you, nothing extra. The only exception are Indian spices, you can assume
those even if they are not a part of the list.
2. Before even deciding on the recipe, categorize the items into their suitable utility - whether they are better as a sweet, or a savory
ingredient, whether or not you will be making a salad, a main course, a starter, a dessert, a sweet dish, or a casual snack, etc. Only when
you precisely categorize ingredients and the recipe, you will be able to correctly craft a dish.
3. Avoid using every single ingredient altogether. Incline more towards picking certain items that fit better for a recipe over certain others.
4. The dish has to be preferrably in an Indian context. Since you are aware of the taste of Indian culture, your recipes must preferrably fall into this category. If the ingredients belong to a Western Cuisine and you just cannot whip up any Indian recipe using those, only then you can create a Western recipe.
5. Provide a short, concise name for the recipe, not more than 2-3 words.
6. Your output MUST be in the format as shown below. If the ingredients are western, return a western recipe, but do NOT deny to provide a dictionary output at ANY COST.
7. You will be provided a list of recipes that the user already knows of. Your job is to suggest something other than those recipes. THIS IS VERY VERY IMPORTANT, ALWAYS REMEMBER THIS.
8. NEVER EVER VIOLATE THE ABOVE RULES, AT ANY COST.

This is exactly how your output should be formatted :

{"recipe_name":"","ingredients":[...],"instructions":""}

The first key should be named "recipe_name", DO NOT CHANGE IT. Its value must be correct recipe name.
The second key should be named "ingredients", DO NOT CHANGE IT. Its value must be the appropriate ingredients used in the recipe itself.
The third key should be named "instructions", DO NOT CHANGE IT. Its value must the instructions on how to make the recipe, in markdown style format.

INGREDIENTS :
"""

fixer_prompt = """
        Provided to you will be a string that looks like a JSON dictionary. This dictionary was to be loaded into a Python dictionary using json.dumps() but failed. The error thrown during this process is also given to you. Your main mission is to fix this error by modifying the string's JSON syntax in such a way that json.dumps() won't throw any errors. In other words, fix the incorrect syntax of the JSON within the string, and provide the corrected version as the output.

        GOLDEN RULES :

        1. Apart from the corrected JSON string, DO NOT return anything else, no unnecessary characters, headers, backticks, symbols, escape sequences, texts, etc.
        2. Never ever break Golden Rule Number 1.

        Here's the flawed JSON string :
        """


def get_recipe(ingreds, recipe_list):
    recipe_res = recipe_model.generate_content(
        f"{recipe_prompt}\n{ingreds}\nLIST OF RECIPES THAT YOU SHOULD NOT SUGGEST:\n{recipe_list}").text
    try:
        recipe = json.loads(recipe_res)
    except Exception as e:
        rpm = recipe_model.generate_content(
            f"{fixer_prompt}\n{recipe_res}\nHere's the error:\n{e}").text
        recipe = json.loads(rpm)
    return recipe


def get_image_links(query):
    imgls = bing_image_urls(query, limit=4)
    return imgls


def get_yt_links(recname):
    urls = []
    dn = recname
    search_term = f"{dn} recipe"
    food = search_term.replace(" ", "+")
    html = urllib.request.urlopen(
        f"https://www.youtube.com/results?search_query={food}")
    vid_urls = set(re.findall(r"watch\?v=(\S{11})", html.read().decode()))
    unique_vid_urls = list(vid_urls)
    for i in range(len(unique_vid_urls[:4])):
        current = f"https://www.youtube.com/watch?v={unique_vid_urls[i]}"
        urls.append(current)
    return urls


def let_him_cook(q, recipe_history):
    try:
        query = vision_model.generate_content(
            [ingredients_vision_prompt, q]).text
    except Exception as e:
        print(e)
        query = q

    recipe = get_recipe(query, recipe_history)
    img_ls = get_image_links(recipe["recipe_name"])
    yt_links = get_yt_links(recipe["recipe_name"])

    final_output = {
        "recipe": recipe,
        "images": img_ls,
        "yt_videos": yt_links
    }

    return final_output


@app.post("/from-text/")
async def get_recipe_from_text(text: str, recipe_history: List[str]=[]):
    result = let_him_cook(q=text, recipe_history=recipe_history)
    return result


@app.get("/keep-alive/")
async def keep_alive():
    statement = "Successfully activated the PocketChef API!"
    print(statement)
    return statement

@app.post("/from-image/")
async def post_recipe_from_image(file: UploadFile = File(...), recipe_history: List[str]=[]):
    image_data = await file.read()
    image = Image.open(BytesIO(image_data))
    result = let_him_cook(q=image, recipe_history=recipe_history)
    return result
