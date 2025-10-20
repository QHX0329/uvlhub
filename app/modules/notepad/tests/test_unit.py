import pytest

from app import db
from app.modules.auth.models import User
from app.modules.notepad.models import Notepad
from app.modules.notepad.repositories import NotepadRepository
from app.modules.notepad.services import NotepadService
from app.modules.conftest import login, logout


@pytest.fixture(scope='module')
def test_client(test_client):
    """Extend the base test_client fixture for module-specific setup."""
    with test_client.application.app_context():
        user_test = User(email="user@example.com", password="test1234")
        db.session.add(user_test)
        db.session.commit()
    
    yield test_client

def test_list_empty_notepad_get(test_client):
    """
    Tests access to the empty notepad list via GET request.
    """
    login_response = login(test_client, "user@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful."

    response = test_client.get("/notepad")
    assert response.status_code == 200, "The notepad page could not be accessed."
    assert b"You have no notepads." in response.data, "The expected content is not present on the page"

    logout(test_client)


def test_repository_create_and_count():
    repo = NotepadRepository()
    initial = repo.count()
    n = repo.create(title="Comprar pan", body="Ir a la tienda", user_id=1)
    assert n.id is not None
    assert repo.count() == initial + 1


def test_repository_get_by_id():
    repo = NotepadRepository()
    n = repo.create(title="Tarea", body="Contenido", user_id=2)
    fetched = repo.get_by_id(n.id)
    assert fetched is not None
    assert fetched.title == "Tarea"


def test_service_get_all_by_user_returns_list():
    service = NotepadService()
    # ensure no notepads for user 999
    res = service.get_all_by_user(999)
    assert isinstance(res, list)


def test_notepad_routes_index_requires_login(test_client):
    # Accessing the index without login should redirect
    resp = test_client.get('/notepad', follow_redirects=False)
    assert resp.status_code in (301, 302)


def test_create_notepad_via_routes_and_view(test_client):
    # Login as default test user from conftest
    login_resp = login(test_client, "test@example.com", "test1234")
    assert login_resp.status_code == 200

    # Create a notepad via POST
    rv = test_client.post('/notepad/create', data=dict(title='Nota prueba', body='Contenido'), follow_redirects=True)
    assert rv.status_code == 200

    # Ensure created in DB
    np = Notepad.query.filter_by(title='Nota prueba').first()
    assert np is not None

    # View the created notepad
    show = test_client.get(f'/notepad/{np.id}')
    assert show.status_code == 200
    assert b'Nota prueba' in show.data

    # Edit the notepad
    edit = test_client.post(f'/notepad/edit/{np.id}', data=dict(title='Nota editada', body='Nuevo'), follow_redirects=True)
    assert edit.status_code == 200

    # Delete the notepad
    delete = test_client.post(f'/notepad/delete/{np.id}', follow_redirects=True)
    assert delete.status_code == 200

    # Logout
    logout(test_client)
