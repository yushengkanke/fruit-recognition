import os

import sqlalchemy
from sqlalchemy import create_engine,text
from sqlalchemy.exc import IntegrityError
from security import hash_password, is_password_hash, verify_password

# 默认仍是项目目录下的 app.db（本地照旧）；
# Docker 里通过 DATABASE_URL 指到 /app/data/app.db，数据才会落在挂载卷里
# echo=False + hide_parameters=True：不把密码 / API Key 等绑定参数写进 SQL 日志
engine = create_engine(
    os.getenv("DATABASE_URL", "sqlite:///app.db"),
    echo=False,
    hide_parameters=True,
)

# connection = engine.connect()


# connection.execute(text("create table if not exists records (user_id str,in_photo str,out_photo str,ai_text text)"))
# connection.commit()

# connection.close()
def createuser(id:str,name:str,password:str,apikey:str , base_url:str , u_model:str):
    # engine = create_engine("sqlite:///app.db",echo=True)
    password_hash = hash_password(password)
    conn = engine.connect()
    try:
       # n = conn.execute(text("select count(*) from users where id = :id"),{"id":id})
       conn.execute(text("insert into users (id,name,password,APIkey,base_url,u_model) values (:id,:name,:password,:apikey,:base_url,:u_model)"),
                    {"id": id, "name": name, "password": password_hash, "apikey": apikey,"base_url": base_url, "u_model": u_model})
       conn.commit()
    except IntegrityError:
        raise ValueError(f"{id}已经存在")

    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"用户创建失败:{str(e)}")
    finally:
        conn.close()

def login (id:str,password:str):
    conn = engine.connect()
    y = conn.execute(text("select id,name,password from users where id = :id"),{"id":id})
    yy = y.mappings().first()

    conn.close()
    if yy is None:
        return {"description":"用户不存在"}
    if not verify_password(password, yy["password"]):
        return {"description":"密码不正确"}
    return {"id":id,"name":yy["name"]}

def switch_user(id:str,password:str):
    return login(id,password)

def alter_KEY(APIkey:str,id:str):
    conn = engine.connect()
    conn.execute(text("update users set APIkey = :API where id = :id"),{"API":APIkey,"id":id})
    conn.commit()
    conn.close()

def change_model(id:str,base_url:str,u_model:str):
    conn = engine.connect()
    conn.execute(text("update users set base_url = :base_url, u_model = :u_model where id = :id"),{"base_url":base_url,"id":id,"u_model":u_model})
    conn.commit()
    conn.close()

def getuser(id:str):
    conn = engine.connect()
    try:
        us = conn.execute(text("select * from users where id = :id"),{"id":id})
        return us.mappings().first()
    finally:
        conn.close()

def upload_work(user_id:str,in_photo:str,out_photo1:str,out_photo2: str,ai_text:str):
    conn = engine.connect()
    conn.execute(text("insert into records (user_id ,in_photo,out_photo1,out_photo2,ai_text) values (:user_id,:in_photo,:out_photo1,:out_photo2,:ai_text)"),
                 {"user_id":user_id,"in_photo":in_photo,"out_photo1":out_photo1,"out_photo2":out_photo2,"ai_text":ai_text})
    conn.commit()
    conn.close()

def select_work(user_id:str):
    conn = engine.connect()
    temp = conn.execute(text("select * from records where user_id = :user_id order by r_id desc"),{"user_id":user_id})
    ans = [dict(row._mapping) for row in temp]
    conn.close()
    return ans

def media_owner(task_id:str,filename:str):
    """按图片 URL 反查记录所有者，供 /media 鉴权使用。"""
    url = f"/media/{task_id}/{filename}"
    conn = engine.connect()
    try:
        row = conn.execute(
            text("select user_id from records where in_photo = :url or out_photo1 = :url or out_photo2 = :url order by r_id desc limit 1"),
            {"url": url},
        ).first()
        return row[0] if row is not None else None
    finally:
        conn.close()

def init_db():
    connection = engine.connect()
    connection.execute(text("create table if not exists records (r_id integer primary key autoincrement ,user_id text,in_photo text,out_photo1 text,out_photo2 text,ai_text text)"))
    connection.execute(text("create table if not exists users (id text primary key not null, name text ,password text,APIkey text ,base_url text , u_model text)"))
    # 把旧库里的明文密码迁移成 bcrypt 哈希
    rows = connection.execute(text("select id,password from users")).mappings().all()
    for row in rows:
        stored = row["password"] or ""
        if is_password_hash(stored):
            continue
        connection.execute(
            text("update users set password = :password where id = :id"),
            {"password": hash_password(stored), "id": row["id"]},
        )
    connection.commit()
    connection.close()
if __name__ == "__main__":
   # engine = create_engine("sqlite:///app.db", echo=True)
   # connection = engine.connect()
   # engine = create_engine("sqlite:///app.db", echo=True)
    init_db()
    connection = engine.connect()

    connection.commit()
    connection.close()
