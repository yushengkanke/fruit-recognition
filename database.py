import sqlalchemy
from sqlalchemy import create_engine,text
from sqlalchemy.exc import IntegrityError
engine = create_engine("sqlite:///app.db",echo =True)

# connection = engine.connect()


# connection.execute(text("create table if not exists records (user_id str,in_photo str,out_photo str,ai_text text)"))
# connection.commit()

# connection.close()
def createuser(id:str,name:str,password:str,apikey:str):
    # engine = create_engine("sqlite:///app.db",echo=True)
    conn = engine.connect()
    try:
       # n = conn.execute(text("select count(*) from users where id = :id"),{"id":id})
       conn.execute(text("insert into users (id,name,password,APIkey) values (:id,:name,:password,:apikey)"),
                    {"id": id, "name": name, "password": password, "apikey": apikey})
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
        return None
    if password !=yy.password:
        return None
    return {"id":id,"name":yy["name"]}

def switch_user(id:str,password:str):
    return login(id,password)

def alter_KEY(APIkey:str,id:str):
    conn = engine.connect()
    conn.execute(text("update users set Apikey = :API where id = :id"),{"API":APIkey,"id":id})
    conn.commit()
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

def init_db():
    connection = engine.connect()
    connection.execute(text("create table if not exists records (r_id integer primary key autoincrement ,user_id text,in_photo text,out_photo1 text,out_photo2 text,ai_text text)"))
    connection.execute(text("create table if not exists users (id text primary key not null, name text ,password text,APIkey text )"))
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



