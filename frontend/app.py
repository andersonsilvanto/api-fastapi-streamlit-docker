import os

import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001").rstrip("/")

st.set_page_config(page_title="Items - app_v2", page_icon="📦")
st.title("Items")
st.caption("Interface Streamlit ligada à API FastAPI.")

with st.form("create_item", clear_on_submit=True):
    name = st.text_input("Nome")
    description = st.text_area("Descrição")
    submitted = st.form_submit_button("Criar item")

if submitted:
    if not name.strip():
        st.warning("Informe o nome do item.")
    else:
        try:
            response = requests.post(
                f"{API_BASE_URL}/items/",
                json={"name": name.strip(), "description": description.strip() or None},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            st.error(f"Não foi possível criar o item: {error}")
        else:
            st.success("Item criado.")
            st.rerun()

st.subheader("Itens cadastrados")

try:
    response = requests.get(f"{API_BASE_URL}/items/", timeout=10)
    response.raise_for_status()
except requests.RequestException as error:
    st.error(f"Não foi possível carregar os itens da API: {error}")
else:
    items = response.json()
    if items:
        st.dataframe(items, use_container_width=True, hide_index=True)
    else:
        st.info("Ainda não há itens cadastrados.")
