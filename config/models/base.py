from pydantic import BaseModel, Field, constr, model_validator, EmailStr


class Base(BaseModel):
    class Config:
        from_attributes = True
        extra = "ignore"
        arbitrary_types_allowed = True

    def model_name(self):
        return self.__class__.__name__