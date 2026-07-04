from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Field, create_engine, Session, select
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import os

load_dotenv()

# ---------- DATABASE MODELS ----------

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str


class Client(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: Optional[str] = None


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    client_id: int = Field(foreign_key="client.id")


class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    completed: bool = False
    project_id: int = Field(foreign_key="project.id")


class ClientMember(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id")
    user_id: int = Field(foreign_key="user.id")
    role: str = "member"


# ---------- INPUT MODELS ----------

class UserCreate(SQLModel):
    username: str
    password: str

class ClientCreate(SQLModel):
    name: str
    email: Optional[str] = None

class ProjectCreate(SQLModel):
    name: str

class TaskCreate(SQLModel):
    title: str
    description: Optional[str] = None
    completed: bool = False

class TaskPatch(SQLModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None

class InviteRequest(SQLModel):
    username: str


# ---------- AUTH SETUP ----------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 180


def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if user is None:
            raise credentials_exception
        return user


# ---------- PERMISSION HELPERS ----------

def is_client_member(client_id: int, user_id: int, session: Session) -> bool:
    membership = session.exec(
        select(ClientMember).where(
            ClientMember.client_id == client_id,
            ClientMember.user_id == user_id
        )
    ).first()
    return membership is not None


def is_client_owner(client_id: int, user_id: int, session: Session) -> bool:
    membership = session.exec(
        select(ClientMember).where(
            ClientMember.client_id == client_id,
            ClientMember.user_id == user_id
        )
    ).first()
    return membership is not None and membership.role == "owner"


def get_owned_project(project_id: int, current_user: User, session: Session):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    client = session.get(Client, project.client_id)
    if not client or not is_client_member(client.id, current_user.id, session):
        raise HTTPException(status_code=404, detail="Project not found")

    return project


# ---------- DATABASE + APP SETUP ----------

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SQLModel.metadata.create_all(engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ledger-frontend-xxxx.onrender.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- AUTH ENDPOINTS ----------

@app.post("/register")
def register(user: UserCreate):
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.username == user.username)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")

        new_user = User(username=user.username, hashed_password=hash_password(user.password))
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return {"message": "User created successfully", "user_id": new_user.id}


@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == form_data.username)).first()

        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Incorrect username or password")

        access_token = create_access_token(data={"sub": user.username})
        return {"access_token": access_token, "token_type": "bearer"}


@app.delete("/me")
def delete_account(current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        my_memberships = session.exec(
            select(ClientMember).where(ClientMember.user_id == current_user.id)
        ).all()

        for membership in my_memberships:
            client_id = membership.client_id
            was_owner = membership.role == "owner"
            session.delete(membership)
            session.commit()

            remaining = session.exec(
                select(ClientMember).where(ClientMember.client_id == client_id)
            ).all()

            if not remaining:
                projects = session.exec(select(Project).where(Project.client_id == client_id)).all()
                for project in projects:
                    tasks = session.exec(select(Task).where(Task.project_id == project.id)).all()
                    for task in tasks:
                        session.delete(task)
                    session.delete(project)
                client = session.get(Client, client_id)
                session.delete(client)
                session.commit()
            elif was_owner:
                new_owner = remaining[0]
                new_owner.role = "owner"
                session.commit()

        user = session.get(User, current_user.id)
        session.delete(user)
        session.commit()
        return {"message": "Account deleted"}


# ---------- CLIENT ENDPOINTS ----------

@app.post("/clients")
def create_client(client: ClientCreate, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        db_client = Client(name=client.name, email=client.email)
        session.add(db_client)
        session.commit()
        session.refresh(db_client)

        membership = ClientMember(client_id=db_client.id, user_id=current_user.id, role="owner")
        session.add(membership)
        session.commit()
        session.refresh(db_client)

        return db_client


@app.get("/clients")
def get_clients(current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        statement = select(Client).join(ClientMember).where(ClientMember.user_id == current_user.id)
        return session.exec(statement).all()


@app.delete("/clients/{client_id}")
def delete_client(client_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        client = session.get(Client, client_id)
        if not client or not is_client_member(client_id, current_user.id, session):
            raise HTTPException(status_code=404, detail="Client not found")

        if not is_client_owner(client_id, current_user.id, session):
            raise HTTPException(status_code=403, detail="Only the owner can delete this client")

        projects = session.exec(select(Project).where(Project.client_id == client_id)).all()
        for project in projects:
            tasks = session.exec(select(Task).where(Task.project_id == project.id)).all()
            for task in tasks:
                session.delete(task)
            session.delete(project)

        memberships = session.exec(select(ClientMember).where(ClientMember.client_id == client_id)).all()
        for membership in memberships:
            session.delete(membership)

        session.delete(client)
        session.commit()
        return {"message": "Client deleted"}


# ---------- ACCESS MANAGEMENT ----------

@app.post("/clients/{client_id}/invite")
def invite_member(client_id: int, invite: InviteRequest, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        client = session.get(Client, client_id)
        if not client or not is_client_member(client_id, current_user.id, session):
            raise HTTPException(status_code=404, detail="Client not found")

        invited_user = session.exec(select(User).where(User.username == invite.username)).first()
        if not invited_user:
            raise HTTPException(status_code=404, detail="No user found with that username")

        if is_client_member(client_id, invited_user.id, session):
            raise HTTPException(status_code=400, detail="User already has access")

        membership = ClientMember(client_id=client_id, user_id=invited_user.id, role="member")
        session.add(membership)
        session.commit()
        return {"message": f"{invite.username} added to client"}


@app.get("/clients/{client_id}/members")
def get_client_members(client_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        client = session.get(Client, client_id)
        if not client or not is_client_member(client_id, current_user.id, session):
            raise HTTPException(status_code=404, detail="Client not found")

        statement = select(User).join(ClientMember).where(ClientMember.client_id == client_id)
        return session.exec(statement).all()


@app.delete("/clients/{client_id}/members/{user_id}")
def remove_member(client_id: int, user_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        client = session.get(Client, client_id)
        if not client or not is_client_member(client_id, current_user.id, session):
            raise HTTPException(status_code=404, detail="Client not found")

        if not is_client_owner(client_id, current_user.id, session):
            raise HTTPException(status_code=403, detail="Only the owner can remove members")

        member_count = len(session.exec(
            select(ClientMember).where(ClientMember.client_id == client_id)
        ).all())

        if member_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last member of a client")

        membership = session.exec(
            select(ClientMember).where(
                ClientMember.client_id == client_id,
                ClientMember.user_id == user_id
            )
        ).first()

        if not membership:
            raise HTTPException(status_code=404, detail="This user does not have access")

        session.delete(membership)
        session.commit()
        return {"message": "Member removed"}


@app.post("/clients/{client_id}/leave")
def leave_client(client_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        my_membership = session.exec(
            select(ClientMember).where(
                ClientMember.client_id == client_id,
                ClientMember.user_id == current_user.id
            )
        ).first()

        if not my_membership:
            raise HTTPException(status_code=404, detail="Client not found")

        all_members = session.exec(
            select(ClientMember).where(ClientMember.client_id == client_id)
        ).all()

        if len(all_members) <= 1:
            raise HTTPException(status_code=400, detail="Cannot leave — you're the last member. Delete the client instead.")

        was_owner = my_membership.role == "owner"

        session.delete(my_membership)
        session.commit()

        if was_owner:
            remaining = session.exec(
                select(ClientMember).where(ClientMember.client_id == client_id)
            ).all()
            new_owner = remaining[0]
            new_owner.role = "owner"
            session.commit()

        return {"message": "You have left this client"}


# ---------- PROJECT ENDPOINTS ----------

@app.post("/clients/{client_id}/projects")
def create_project(client_id: int, project: ProjectCreate, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        client = session.get(Client, client_id)
        if not client or not is_client_member(client_id, current_user.id, session):
            raise HTTPException(status_code=404, detail="Client not found")

        db_project = Project(name=project.name, client_id=client_id)
        session.add(db_project)
        session.commit()
        session.refresh(db_project)
        return db_project


@app.get("/clients/{client_id}/projects")
def get_projects_for_client(client_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        client = session.get(Client, client_id)
        if not client or not is_client_member(client_id, current_user.id, session):
            raise HTTPException(status_code=404, detail="Client not found")

        statement = select(Project).where(Project.client_id == client_id)
        return session.exec(statement).all()


# ---------- TASK ENDPOINTS ----------

@app.post("/projects/{project_id}/tasks")
def create_task(project_id: int, task: TaskCreate, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        get_owned_project(project_id, current_user, session)

        db_task = Task(**task.model_dump(), project_id=project_id)
        session.add(db_task)
        session.commit()
        session.refresh(db_task)
        return db_task


@app.get("/projects/{project_id}/tasks")
def get_tasks_for_project(project_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        get_owned_project(project_id, current_user, session)

        statement = select(Task).where(Task.project_id == project_id)
        return session.exec(statement).all()


@app.get("/tasks/{task_id}")
def get_task(task_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        get_owned_project(task.project_id, current_user, session)
        return task


@app.patch("/tasks/{task_id}")
def patch_task(task_id: int, updated_task: TaskPatch, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        get_owned_project(task.project_id, current_user, session)

        if updated_task.title is not None:
            task.title = updated_task.title
        if updated_task.description is not None:
            task.description = updated_task.description
        if updated_task.completed is not None:
            task.completed = updated_task.completed

        session.commit()
        session.refresh(task)
        return task


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, current_user: User = Depends(get_current_user)):
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        get_owned_project(task.project_id, current_user, session)

        session.delete(task)
        session.commit()
        return {"message": "Task deleted"}
    