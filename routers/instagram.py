from fastapi import APIRouter

import dependencies

router = APIRouter()


@router.get('/getPhotos')
def get_photos(username: str, max_count: int):
    return {'urls': dependencies.get_photos(username, max_count)}
