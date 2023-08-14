import os
from email.utils import formatdate
from mimetypes import guess_type
from pathlib import Path
from typing import Dict, Annotated, Union

from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from application.api.dp import get_db
from application.api.v1.user.models import User
from application.api.v1.user.schema import UserInDB, CreateUser, UpdateUser
from application.api.v1.user.server import crud_user
from application.extension.utils.response import CustomResponse
from application.extension.utils.security import create_access_token, verify_password, get_password_hash, \
    get_current_user

router = APIRouter(prefix="/user", tags=["用户"])


@router.post("/token", response_model=Dict, summary="Token获取接口")
def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db)
) -> Dict:
    user = crud_user.get_user_by_phone(db=db, phone=form_data.username)
    if not user or not verify_password(plain_password=form_data.password, hashed_password=user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.phone})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/", response_model=CustomResponse[UserInDB], summary="用户创建接口")
def create_user(
        user_in: CreateUser,
        db: Session = Depends(get_db)
) -> CustomResponse:
    old_user = crud_user.get_user_by_phone(db=db, phone=user_in.phone)
    if old_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号已经被注册。"
        )
    # 将明文密码加密再存放到数据库当中
    user_in.password = get_password_hash(user_in.password)
    user = crud_user.create(db=db, object_in=user_in)
    return CustomResponse(data=user)


@router.get("/me/", response_model=CustomResponse[UserInDB], summary="根据Token获取用户信息")
def read_user_me(current_user: User = Depends(get_current_user)) -> CustomResponse:
    return CustomResponse(data=current_user)


@router.get("/{id_}", response_model=CustomResponse[UserInDB], summary="根据用户ID获取用户信息")
def read_user_by_id(id_: int, db: Session = Depends(get_db)) -> CustomResponse:
    user = crud_user.get(db=db, id_=id_)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="错误ID。"
        )
    return CustomResponse(data=user)


@router.delete("/{id_}", response_model=CustomResponse[UserInDB], summary="根据用户ID删除用户")
def remove_user_by_id(id_: int, db: Session = Depends(get_db)) -> CustomResponse:
    user = crud_user.get(db=db, id_=id_)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="错误ID。"
        )
    user = crud_user.remove(db=db, id_=id_)
    return CustomResponse(data=user)


@router.put("/", response_model=CustomResponse[UserInDB], summary="根据ID更新用户信息")
def update_user_by_id(user_in: UpdateUser, db: Session = Depends(get_db)) -> CustomResponse:
    user_in_db = crud_user.get(db=db, id_=user_in.id)
    if not user_in_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="错误ID。"
        )
    if user_in.password:
        user_in.password = get_password_hash(user_in.password)
    new_user = crud_user.update(db=db, db_obj=user_in_db, obj_in=user_in)
    return CustomResponse(data=new_user)


@router.get("/download/file")
def download_file():
    from fastapi.responses import FileResponse
    return FileResponse(path="D:\\Download.zip", filename="Download.zip")


@router.head("/download/file")
def get_file_size():
    file_size = Path("D:\\Download.zip").stat().st_size
    response = Response()
    response.headers['Content-Length'] = str(file_size)
    return response


@router.head("/download/file/streaming")
def get_file_size():
    file_size = Path("D:\\Download.zip").stat().st_size
    response = Response()
    response.headers['Content-Length'] = str(file_size)
    response.headers['Accept-Ranges'] = "bytes"
    return response


def file_iterator(file_path, offset, chunk_size):
    """
    文件生成器
    :param file_path: 文件绝对路径
    :param offset: 文件读取的起始位置
    :param chunk_size: 文件读取的块大小
    :return: yield
    """
    with open(file_path, 'rb') as f:
        f.seek(offset, os.SEEK_SET)
        while True:
            data = f.read(chunk_size)
            if data:
                yield data
            else:
                break


@router.get("/download/file/streaming")
def download_file_with_streaming(range_header: Annotated[Union[str, None], Header()] = None):
    # todo 校验文件是否存在
    print(range_header)
    content_type, encoding = guess_type("D:\\Download.zip")
    content_type = content_type if content_type else "application/octet-stream"
    file_size = int(get_file_size().headers.get("Content-Length"))
    if range_header:
        range_start, range_end = range_header.strip().split("=")[1].split("-")
        start = int(range_start)
        end = int(range_end) if range_end else file_size - 1
        content_length = file_size - start
        if start > end or start > file_size:
            raise HTTPException(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE, detail="Range Not Satisfiable"
            )
        headers = {
            'content-disposition': f'attachment; filename="Download.zip"',
            'accept-ranges': 'bytes',
            'connection': 'keep-alive',
            'content-length': str(content_length),
            'content-range': f'bytes {start}-{end}/{file_size}',
            'last-modified': formatdate(Path("D:\\Download.zip").stat().st_mtime, usegmt=True),
        }
        response = StreamingResponse(
            file_iterator("D:\\Download.zip", start, 1024 * 1024 * 1),
            media_type=content_type,
            headers=headers, status_code=206 if start > 0 else 200
        )
        return response
