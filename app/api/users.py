from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import User
from app.schemas import UserResponse, UserUpdate, UserPasswordUpdate, UserListResponse, HistoryListResponse, SessionListResponse
from app.services import UserService, HistoryService, SessionService, AuthService
from app.api.deps import get_current_user, get_current_admin

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    users = await user_service.get_all_users_paginated(skip, limit)
    total = await user_service.count_users()
    return UserListResponse(users=users, total=total)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    updated_user = await user_service.update_user(current_user.id, user_data)
    return updated_user


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    password_data: UserPasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    success = await user_service.update_password(current_user.id, password_data)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )


@router.get("/me/history", response_model=HistoryListResponse)
async def get_my_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    history_service = HistoryService(db)
    history, total = await history_service.get_user_history(current_user.id, limit, offset)
    return HistoryListResponse(history=history, total=total)


@router.get("/me/sessions", response_model=SessionListResponse)
async def get_my_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session_service = SessionService(db)
    sessions = await session_service.get_user_sessions(current_user.id)
    return SessionListResponse(sessions=sessions, total=len(sessions))


@router.delete("/me/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)
    session_service = SessionService(db)

    sessions = await session_service.get_user_sessions(current_user.id)
    session = next((s for s in sessions if s.id == session_id), None)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    await auth_service.revoke_session(session.token_jti, current_user.id)


@router.delete("/me/sessions", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)
    await auth_service.revoke_all_sessions(current_user.id)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    user = await user_service.update_user(user_id, user_data, current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    success = await user_service.delete_user(user_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )