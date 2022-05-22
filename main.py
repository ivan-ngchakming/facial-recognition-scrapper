import json
import math

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


API_URL = "http://localhost:5000"

BASE_URL = "https://www.imdb.com"

MAX_RESULT_PER_PAGE = 50
URL = f"{BASE_URL}/search/name/?adult=include&count=250"

TOTAL = 11_922_407
PAGES = int(math.ceil(TOTAL / MAX_RESULT_PER_PAGE))


def get_full_img_url(url):
    """
    'https://m.media-amazon.com/images/M/MV5BMjA4NDkyODA3M15BMl5BanBnXkFtZTgwMzUzMjYzNzM@._V1_UY209_CR34,0,140,209_AL_.jpg'
    to
    https://m.media-amazon.com/images/M/MV5BMjA4NDkyODA3M15BMl5BanBnXkFtZTgwMzUzMjYzNzM@.jpg
    """
    base_path = url.split("._V1_")[0]
    ext = url.split(".")[-1]
    return base_path + "." + ext


def get_or_create_profile(data):
    r = requests.get(
        API_URL + f'/profiles?sort=created_date,desc&filter.name=$eq:{data["name"]}'
    )
    res = json.loads(r.text)
    if int(res["meta"]["total"]) >= 1:
        return res["data"][0]

    profile_data = {
        "name": data["name"],
        "first_name": data["firstname"],
        "last_name": data["lastname"],
        "middle_name": data["middlename"],
        "attributes": {
            "imdb": data["source"],
        },
    }
    
    if "birth" in data:
        profile_data["birth"] = data["birth"]
    if "birth_place" in data:
        profile_data["attributes"]["birth_place"] = data["birth_place"]
        
    r = requests.post(
        API_URL + "/profiles",
        json=profile_data,
    )
    return json.loads(r.text)


def main(start_page=0):
    with tqdm(total=TOTAL) as pbar:
        with open('downloaded.txt', 'w+') as f:
            downloaded = [line.split('\t')[1] for line in f.readlines()]
            
            for page in range(start_page, PAGES):

                r = requests.get(URL + f"start={page*MAX_RESULT_PER_PAGE+1}")
                soup = BeautifulSoup(r.content, "html.parser")

                items = soup.find_all(attrs={"class": "lister-item mode-detail"})

                for item_idx, item in enumerate(items):
                    pbar.set_description(f"{page}:{item_idx}")
                    
                    image_url = get_full_img_url(item.img.get("src"))
                    actor_page_url = BASE_URL + item.a.get("href")

                    if actor_page_url in downloaded:
                        continue
                    
                    actor_page_r = requests.get(actor_page_url)
                    actor_page_soup = BeautifulSoup(actor_page_r.content, "html.parser")

                    # Name
                    name = actor_page_soup.title.text.replace(" - IMDb", "")
                    firstname, *middlename, lastname = name.split(" ")
                    middlename = " ".join(middlename)

                    pbar.set_description(f"{page}:{item_idx} - {name}")
                    
                    data = {
                        "name": name,
                        "firstname": firstname,
                        "middlename": middlename,
                        "lastname": lastname,
                        "source": actor_page_url,
                        "image": image_url,
                    }
                        
                    # Birth date and place
                    born_info = actor_page_soup.find(id="name-born-info")
                    try:
                        data["birth"] = born_info.time.get("datetime")
                    except AttributeError:
                        pass
                    
                    try:
                        data["birth_place"] = born_info.find_all("a")[-1].text
                    except AttributeError:
                        pass
                    
                    profile = get_or_create_profile(data)
                    if profile["updated_date"] != profile["created_date"]:
                        continue

                    r = requests.post(API_URL + "/photos", json={"url": data["image"]})
                    photo = json.loads(r.text)
                    if "error" not in photo:
                        for face in photo["faces"]:
                            requests.patch(
                                API_URL + f'/faces/{face["id"]}',
                                json={"profile_id": profile["id"]},
                            )

                    f.write(data["name"] + '\t' + actor_page_url + '\n')
                    pbar.update(1)


if __name__ == "__main__":
    main()
