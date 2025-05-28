from pydantic import BaseModel

class MovieCreate(BaseModel):
    title: str

class MovieResponse(BaseModel):
    id: int
    title: str
    duration: int

    class Config:
        from_attributes = True
