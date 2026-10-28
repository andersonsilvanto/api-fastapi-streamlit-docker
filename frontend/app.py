import os

import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001").rstrip("/")
IS_DEVELOPMENT = os.getenv("APP_ENV", "production").lower() == "development"

st.set_page_config(page_title="AgroTech Enterprise", page_icon="🌱")
st.title("AgroTech Enterprise")
st.caption("Interface Streamlit ligada à API FastAPI.")


def api_error(response: requests.Response) -> str:
    try:
        detail = response.json().get("detail", "Unknown API error")
    except (ValueError, AttributeError):
        detail = response.text or "Unknown API error"
    return str(detail)


def clear_authentication() -> None:
    for key in ("access_token", "username", "must_change_password"):
        st.session_state.pop(key, None)


if not st.session_state.get("access_token"):
    with st.form("login"):
        username = st.text_input("Utilizador", value="admin")
        password = st.text_input(
            "Senha",
            value="1234" if IS_DEVELOPMENT else "",
            type="password",
        )
        login_submitted = st.form_submit_button("Entrar")

    if login_submitted:
        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/login",
                json={"username": username.strip(), "password": password},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            if error.response is not None:
                st.error(f"Falha na autenticação: {api_error(error.response)}")
            else:
                st.error(f"Não foi possível contactar a API: {error}")
        else:
            login_result = response.json()
            st.session_state["access_token"] = login_result["access_token"]
            st.session_state["username"] = username.strip()
            st.session_state["must_change_password"] = login_result[
                "must_change_password"
            ]
            st.rerun()

    st.stop()


access_token = st.session_state["access_token"]
authorization_headers = {"Authorization": f"Bearer {access_token}"}

if st.session_state.get("must_change_password"):

    @st.dialog("Alteração obrigatória de senha")
    def force_password_change() -> None:
        st.warning(
            "A senha inicial não pode ser usada para aceder aos dados. "
            "Defina agora uma senha forte."
        )
        with st.form("force_password_change"):
            current_password = st.text_input("Senha atual", type="password")
            new_password = st.text_input("Nova senha", type="password")
            confirm_password = st.text_input("Confirmar nova senha", type="password")
            submitted = st.form_submit_button("Alterar senha")

        if not submitted:
            return
        if new_password != confirm_password:
            st.error("A confirmação não coincide com a nova senha.")
            return

        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/change-password",
                json={
                    "current_password": current_password,
                    "new_password": new_password,
                },
                headers=authorization_headers,
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            if error.response is not None:
                st.error(f"Não foi possível alterar a senha: {api_error(error.response)}")
            else:
                st.error(f"Não foi possível contactar a API: {error}")
        else:
            result = response.json()
            st.session_state["access_token"] = result["access_token"]
            st.session_state["must_change_password"] = result[
                "must_change_password"
            ]
            st.success("Senha alterada.")
            st.rerun()

    force_password_change()
    st.stop()

st.write(f"Sessão autenticada: **{st.session_state['username']}**")
if st.button("Terminar sessão"):
    clear_authentication()
    st.rerun()

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
                headers=authorization_headers,
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            if error.response is not None:
                st.error(f"Não foi possível criar o item: {api_error(error.response)}")
            else:
                st.error(f"Não foi possível criar o item: {error}")
        else:
            st.success("Item criado.")
            st.rerun()

st.subheader("Itens cadastrados")

try:
    response = requests.get(
        f"{API_BASE_URL}/items/",
        headers=authorization_headers,
        timeout=10,
    )
    response.raise_for_status()
except requests.RequestException as error:
    if error.response is not None:
        st.error(f"Não foi possível carregar os itens: {api_error(error.response)}")
    else:
        st.error(f"Não foi possível carregar os itens: {error}")
else:
    items = response.json()
    if items:
        st.dataframe(items, use_container_width=True, hide_index=True)
    else:
        st.info("Ainda não há itens cadastrados.")
