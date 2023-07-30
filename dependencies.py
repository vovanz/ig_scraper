import json
import logging
import time
import typing
# from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

# from tenacity import retry
import decouple
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

_SELENIUM_HOST = decouple.config("SELENIUM_HOST")

_LINKS_SELECTOR = 'a[href^="/p/"]'
_MORE_BUTTON_XPATH = "/html/body//section//button/div/span"

_WINDOW_WIDTH = 1050
_WINDOW_HEIGHT = 978

_MIN_PHOTO_WIDTH = 500
_MIN_PHOTO_HEIGHT = 400

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("incognito")


@contextmanager
def _driver_context(url: str):
    driver = webdriver.Remote(
        command_executor=f"http://{_SELENIUM_HOST}:4444/wd/hub", options=chrome_options
    )
    try:
        driver.get(url)
        driver.set_window_size(1050, 978)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
        )
        yield driver
    finally:
        driver.quit()


def _get_photo_page_urls(driver: webdriver.Remote) -> typing.List[str]:
    photo_page_links = driver.find_elements(By.CSS_SELECTOR, 'a[href^="/p/"]')
    return [link_element.get_attribute("href") for link_element in photo_page_links]


def _show_more_posts_button_text_lower(username: str):
    return f"Show more posts from {username}".lower()


def _try_to_click_load_more(driver, username):
    for maybe_load_more_btn in driver.find_elements(By.XPATH, _MORE_BUTTON_XPATH):
        if maybe_load_more_btn.text.lower() == _show_more_posts_button_text_lower(
                username
        ):
            driver.execute_script("arguments[0].scrollIntoView()", maybe_load_more_btn)
            maybe_load_more_btn.click()


def _try_to_hide_login_popup(driver: webdriver.Remote):
    for maybe_login_popup in driver.find_elements(
            By.XPATH, '//*[starts-with(@id, "mount_")]/div/div/div[3]'
    ):
        driver.execute_script('arguments[0].style.display = "none";', maybe_login_popup)


def _try_to_scroll_to_the_bottom(driver):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")


def _scroll_and_load_more(driver: webdriver.Remote, username: str):
    _try_to_click_load_more(driver, username)
    _try_to_hide_login_popup(driver)
    _try_to_scroll_to_the_bottom(driver)
    time.sleep(1)


def _load_and_parse_photo_page(photo_url: str):
    urls = []
    prev_step_pics_count = -1
    with _driver_context(photo_url) as driver:
        while True:
            time.sleep(1)
            pics = driver.find_elements(By.CSS_SELECTOR, "img")
            if len(pics) <= prev_step_pics_count:
                break
            else:
                prev_step_pics_count = len(pics)
            for pic in pics:
                try:
                    if (
                            pic.rect["height"] > _MIN_PHOTO_HEIGHT
                            or pic.rect["width"] > _MIN_PHOTO_WIDTH
                    ):
                        photo_url = pic.get_attribute("src")
                        if photo_url is not None and photo_url not in urls:
                            urls.append(photo_url)
                except WebDriverException:
                    continue
    return urls


def get_photos(username: str, max_count: int):
    photo_urls = []
    parsed_page_urls = set()
    with _driver_context(f"https://www.instagram.com/{username}") as driver:
        while len(photo_urls) < max_count:
            logging.info(len(photo_urls))
            photo_page_urls = [
                url
                for url in _get_photo_page_urls(driver)
                if url not in parsed_page_urls
            ]
            photo_page_urls = photo_page_urls[: (max_count - len(photo_urls))]
            for page_url in photo_page_urls:
                photo_urls.extend(_load_and_parse_photo_page(page_url))
            # with ThreadPoolExecutor(max_workers=10) as executor:
            #     futures = [
            #         executor.submit(_load_and_parse_photo_page, url)
            #         for url in photo_page_urls
            #     ]
            #     for future in futures:
            #         photo_urls.extend(future.result())
            parsed_page_urls.update(photo_page_urls)
            if len(photo_urls) < max_count:
                _scroll_and_load_more(driver, username)
    return photo_urls[:max_count]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _urls = get_photos("leomessi", 50)
    print(json.dumps(_urls, indent=4))
