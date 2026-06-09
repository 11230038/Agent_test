import time
import streamlit as st
from agent.react_agent import ReactAgent

# 标题
st.title("扫地机器人智能客服")
st.divider()

if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()
if "message" not in st.session_state:
    st.session_state["message"] = []

for message in st.session_state["message"]:
    if message["role"]=="user":
        st.chat_message("user").write(message["content"])
    else:
        st.chat_message("assistant").write(message["content"])
#用户输入
prompt=st.chat_input()

if prompt:
    st.chat_message("user").write(prompt)
    st.session_state["message"].append({"role": "user", "content": prompt})
    response_message=[]
    with st.spinner("正在思考..."):
        res_stream=st.session_state["agent"].execute_stream(prompt)

        def capture(generator,cache_list):
            for chunk in generator:
                cache_list.append(chunk)
                yield chunk

        st.chat_message("assistant").write(capture(res_stream,response_message))
        st.session_state["message"].append({"role": "assistant", "content": response_message[-1]})


