from pydantic import BaseModel


class EmployeeLoginRequest(BaseModel):
    id: str
    password: str


class EmployeeLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    id: int
    team_code: str
    position_code: str
    permission_code: str


class EmployeeMeResponse(BaseModel):
    id: int
    username: str
    email: str
    team_code: str
    position_code: str
    permission_code: str
    lang_code: str
    countries: list[str] = []


class EmployeeUpdateRequest(BaseModel):
    password: str | None = None
    email: str
    team_code: str
    position_code: str
    lang_code: str
    countries: list[str] = []


class EmailVerifyRequestBody(BaseModel):
    email: str


class EmailVerifyConfirmBody(BaseModel):
    email: str
    code: str


class EmployeeRegisterRequest(BaseModel):
    id: str
    emp_no: str
    password: str
    email: str
    team_code: str
    position_code: str
    permission_code: str
    lang_code: str
    countries: list[str] = []
