import os
from fastapi import FastAPI, File, UploadFile, Form
from typing import Optional
from fxn import Function
from PIL import Image
import base64
from io import BytesIO
import urllib.request
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
a recipe, that is grounded to reality, and caters the taste of Indian audience. DO NOT make up fake recipes, and don't come up with unconventional
combinations such as mixing fruit in spicy dishes, or cooking fruits in oil, etc. Create conventional, pre-existing, traditional indian recipes
from the list of ingredients.

Here are 5 GOLDEN RULES that you MUST adhere to :

1. Your dish MUST use only those ingredients that are provided to you, nothing extra. The only exception are Indian spices, you can assume
those even if they are not a part of the list.
2. Before even deciding on the recipe, categorize the items into their suitable utility - whether they are better as a sweet, or a savory
ingredient, whether or not you will be making a salad, a main course, a starter, a dessert, a sweet dish, or a casual snack, etc. Only when
you precisely categorize ingredients and the recipe, you will be able to correctly craft a dish.
3. Avoid using every single ingredient altogether. Incline more towards picking certain items that fit better for a recipe over certain others.
4. The dish has to be in an Indian context. Since you are aware of the taste of Indian culture, your recipes must strictly fall into this
category.
5. Lastly, provide a short, concise name for the recipe, not more than 2-3 words.

This is exactly how your output should be formatted :

{"recipe_name":"","ingredients":[...],"instructions":""}

INGREDIENTS :
"""

thumbnail_prompt = """
Given to you is a recipe of a dish. Extract the name of this dish, and provide brief visual cues as to how it should look.
Your output should be of the format :

{"dish_name":"","visual_cues":"describe precisely how the dish looks like"}

RECIPE :
"""

def let_him_cook(query):
    if type(query) is str:
        query = query
    else:
        query = vision_model.generate_content([ingredients_vision_prompt, query]).text
    
    recipe_res = recipe_model.generate_content(f"{recipe_prompt}\n{query}").text
    recipe = json.loads(recipe_res)
    thumbnail_description = thumbnail_model.generate_content(f"{thumbnail_prompt}\n{recipe_res}").text
    tdesc = json.loads(thumbnail_description)
    fxn = Function()
    pred = fxn.predictions.create(
        tag="@samplefxn/stable-diffusion",
        inputs={
        "prompt":f"4k, ultra realistic, hd image of : {thumbnail_description}"
        }
    )
    generated_image = pred.results[0]
    byte_stream = BytesIO()
    generated_image.save(byte_stream, format="PNG")
    base64_encoded = base64.b64encode(byte_stream.getvalue())
    base64_string = base64_encoded.decode("utf-8")
    urls = []
    food = tdesc["dish_name"].replace(" ", "+")
    html = urllib.request.urlopen(f"https://www.youtube.com/results?search_query={food}")
    vid_urls = re.findall(r"watch\?v=(\S{11})", html.read().decode())
    for i in range(len(vid_urls[:4])):
        current = f"https://www.youtube.com/watch?v={vid_urls[i]}"
        urls.append(current)
    
    final_output = {
        "recipe":recipe,
        "photo":base64_string,
        "links":urls
    }

    return final_output

@app.get("/get-recipe/")
async def get_recipe_from_text(text: str):
    result = let_him_cook(query=text)
    return result

@app.post("/post-recipe/")
async def post_recipe_from_image(file: UploadFile=File(...)):
    image_data = await file.read()
    image = Image.open(BytesIO(image_data))
    result = let_him_cook(query=image)
    return result