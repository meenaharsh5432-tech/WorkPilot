from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Literal


class TaskCreate(BaseModel):
    user_request: str


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_request: str
    status: str
    result: str | None
    created_at: datetime

class ExecutionStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    step_number: int
    tool_name: str
    input_data: str | None
    output_data: str | None
    status: str
    error_message: str | None
    created_at: datetime




class ApprovalDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = None