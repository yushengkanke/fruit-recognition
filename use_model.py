import os
from openai import OpenAI, api_key

# print("请输入你的图片位置：")
# s = str(input())

# u_model = "deepseek-flash"
# apikey = "sk-088a701fb4f64d51b58564d041b5985b"
# baseurl = "https://api.deepseek.com"
"""def change_model(xu_model:str , xapikey:str , xbaseurl:str):
    u_model = xu_model
    apikey = xapikey
    baseurl = xbaseurl
    return True
"""
def run_model(photo : str , apikey:str , baseurl : str ,u_model : str):
    client = OpenAI(
        api_key= apikey,  # 此APIkey已删除，使用前请在这里填写自己的APIkey
        base_url=baseurl)
    with open(photo, "rb") as f:
        uploaded = client.files.create(file=f, purpose="user_data")

    rt = uploaded.id

    response = client.chat.completions.create(
        model=u_model,
        messages=[
            {"role": "system",
             "content": "You are a helpful assistant"},
            {"role": "user",
             "content": [
                 {"type": "text",
                  "text": "Hello,我现在给你传了一张图片，请为我识别这张图片上的水果是哪一种水果，并且输出它们的个数。"},
                 {"type": "file", "file_id": rt}
             ],
             },
        ],
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}}
    )
    ans = response.choices[0].message.content

    return ans


# print(response.choices[0].message.content)
# ans = response.choices[0].message
# with open("answer.txt","w",encoding="utf-8") as f:
#     f.write(ans.content or "")
# print("答案已经保存到answer.txt中")
