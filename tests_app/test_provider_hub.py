"""User-defined connections, key isolation, and real connector dispatch."""
import json

import pytest
from fastapi.testclient import TestClient

from visual_learning.app import create_app
from visual_learning.providers import ProviderError, SecretStore, make_provider


@pytest.fixture
def hub(tmp_path, monkeypatch):
    keys = {}
    monkeypatch.setattr('keyring.get_password', lambda service, name: keys.get((service, name)))
    monkeypatch.setattr('keyring.set_password', lambda service, name, value: keys.__setitem__((service, name), value))
    monkeypatch.setattr('keyring.delete_password', lambda service, name: keys.pop((service, name), None))
    app = create_app(tmp_path)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        client.headers['x-visual-learning'] = app.state.csrf_token
        client.store = app.state.store
        client.keys = keys
        yield client


def connection(**changes):
    return {'name': 'My custom provider', 'endpoint': 'https://models.example/v1',
            'model': 'my-exact-model-v2', 'protocol': 'openai', **changes}


def add(hub, **changes):
    response = hub.post('/api/connections', json=connection(**changes))
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_multiple_models_from_same_provider_have_independent_connections(hub):
    first = add(hub, api_key='private-first-key')
    second = add(hub, model='another-model', api_key='private-second-key')
    assert first != second
    settings = hub.get('/api/settings').json()
    assert settings['preferences']['api_connections'][first]['model'] == 'my-exact-model-v2'
    assert settings['preferences']['api_connections'][second]['model'] == 'another-model'
    assert settings['credentials'][first]['configured']
    assert SecretStore().get(first) == 'private-first-key'
    assert SecretStore().get(second) == 'private-second-key'
    assert 'private-first-key' not in json.dumps(settings)
    assert 'api_key' not in json.dumps(settings['preferences'])
    for file in hub.store.root.rglob('*'):
        if file.is_file():
            assert b'private-first-key' not in file.read_bytes()


def test_custom_default_is_used_in_job_and_requires_approval(hub):
    name = add(hub)
    assert hub.put('/api/settings', json={'provider': name}).status_code == 200
    denied = hub.post('/api/jobs', json={'url': 'https://youtu.be/jNQXAC9IVRw'})
    assert denied.status_code == 409
    response = hub.post('/api/jobs', json={'url': 'https://youtu.be/jNQXAC9IVRw', 'paid_usage_approved': True})
    assert response.status_code == 201
    preferences = response.json()['job']['input']['preferences']
    assert preferences['provider'] == name
    assert preferences['model'] == 'my-exact-model-v2'
    provider = make_provider(preferences)
    assert provider.name == name
    assert provider.model == 'my-exact-model-v2'
    assert provider.connection['endpoint'] == 'https://models.example/v1'


def test_edit_keeps_saved_key_and_delete_resets_default(hub):
    name = add(hub, api_key='private-key')
    assert hub.put('/api/settings', json={'provider': name}).status_code == 200
    edited = hub.put('/api/connections/' + name, json=connection(name='Renamed', model='second-model'))
    assert edited.status_code == 200
    assert SecretStore().get(name) == 'private-key'
    assert edited.json()['connection']['model'] == 'second-model'
    assert hub.delete('/api/connections/' + name).status_code == 200
    settings = hub.get('/api/settings').json()['preferences']
    assert settings['provider'] == 'codex'
    assert name not in settings['api_connections']
    assert SecretStore().get(name) is None


def test_busy_connection_cannot_change_endpoint_or_remove_key(hub):
    name = add(hub, api_key='private-key')
    job = hub.post('/api/jobs', json={'url': 'https://youtu.be/jNQXAC9IVRw', 'preferences': {'provider': name}, 'paid_usage_approved': True}).json()['job']
    assert hub.put('/api/connections/' + name, json=connection(endpoint='https://different.example/v1', api_key='replacement')).status_code == 409
    assert hub.delete('/api/connections/' + name).status_code == 409
    assert SecretStore().get(name) == 'private-key'
    hub.post('/api/jobs/' + job['id'] + '/cancel')
    assert hub.delete('/api/connections/' + name).status_code == 200


def test_retry_uses_current_connection_and_keeps_only_source(hub):
    name = add(hub, requires_key=False)
    job = hub.post('/api/jobs', json={'url': 'https://youtu.be/jNQXAC9IVRw', 'preferences': {'provider': name}, 'paid_usage_approved': True}).json()['job']
    hub.store.checkpoint(job['id'], 'source', {'text': 'Saved source'})
    hub.store.checkpoint(job['id'], 'knowledge', {'text': 'Old analysis'})
    hub.store.update_job(job['id'], state='failed')
    assert hub.put('/api/connections/' + name, json=connection(model='new-model', requires_key=False)).status_code == 200
    response = hub.post('/api/jobs/' + job['id'] + '/retry', json={'paid_usage_approved': True})
    assert response.status_code == 200
    assert response.json()['input']['preferences']['model'] == 'new-model'
    assert hub.store.load_checkpoint(job['id'], 'source') == {'text': 'Saved source'}
    assert hub.store.load_checkpoint(job['id'], 'knowledge') is None


@pytest.mark.parametrize('changes', [{'name': ' '}, {'model': ' '}, {'endpoint': 'http://remote.example/v1'}, {'endpoint': 'https://user:password@models.example'}, {'protocol': 'unsupported'}, {'api_key': 'private\nkey'}])
def test_invalid_connection_does_not_save_or_echo_a_key(hub, changes):
    response = hub.post('/api/connections', json=connection(**changes))
    assert response.status_code in {400, 422}
    assert 'private\nkey' not in response.text
    assert not hub.store.settings()['api_connections']


def test_unknown_or_reserved_ids_are_rejected(hub):
    assert hub.put('/api/settings', json={'provider': 'not_saved'}).status_code == 409
    assert hub.post('/api/jobs', json={'url': 'https://youtu.be/jNQXAC9IVRw', 'preferences': {'provider': 'not_saved'}, 'paid_usage_approved': True}).status_code == 409
    assert hub.put('/api/settings', json={'api_connections': {'codex': connection()}}).status_code == 422
    assert hub.put('/api/credentials/not_saved', json={'key': 'private-key'}).status_code == 404
    assert hub.put('/api/settings', json={'api_connections': {'bad:id': connection()}}).status_code == 422


@pytest.mark.parametrize('protocol', ['openai', 'anthropic'])
def test_custom_connector_sends_configured_endpoint_model_and_key(hub, monkeypatch, tmp_path, protocol):
    name = add(hub, protocol=protocol, api_key='private-key')
    settings = hub.store.settings() | {'provider': name, 'paid_usage_approved': True}
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        class Response:
            ok, status_code = True, 200
            def json(self):
                if protocol == 'anthropic':
                    return {'content': [{'type': 'text', 'text': '{"answer": true}'}], 'usage': {'output_tokens': 12}, 'stop_reason': 'end_turn'}
                return {'choices': [{'message': {'content': '{"answer": true}'}, 'finish_reason': 'stop'}], 'usage': {'completion_tokens': 12}}
        return Response()

    monkeypatch.setattr('visual_learning.providers.requests.post', post)
    result = make_provider(settings).generate('Source text', {'type': 'object'}, tmp_path)
    assert result.data == {'answer': True}
    assert result.provider == name
    assert calls[0][0] == 'https://models.example/v1' + ('/messages' if protocol == 'anthropic' else '/chat/completions')
    assert calls[0][1]['json']['model'] == 'my-exact-model-v2'
    assert calls[0][1]['headers'].get('x-api-key', calls[0][1]['headers'].get('Authorization')) in {'private-key', 'Bearer private-key'}
    assert calls[0][1]['allow_redirects'] is False


def test_no_key_endpoint_is_explicit_and_legacy_selfhost_is_preserved(hub, monkeypatch, tmp_path):
    name = add(hub, endpoint='http://127.0.0.1:1234/v1', requires_key=False)
    settings = hub.store.settings() | {'provider': name, 'paid_usage_approved': True}
    monkeypatch.setattr('visual_learning.providers.requests.post', lambda *_a, **_k: (_ for _ in ()).throw(ProviderError('sent', 'Reached the request')))
    with pytest.raises(ProviderError, match='Reached the request'):
        make_provider(settings).generate('Source', {}, tmp_path)
    hub.store.save_settings({'api_connections': {'selfhost': {'endpoint': 'http://localhost:1234/v1', 'model': 'old-model'}}})
    assert hub.store.settings()['api_connections']['selfhost']['requires_key'] is False


def test_credential_store_failure_leaves_connection_unsaved(hub, monkeypatch):
    def fail(*_args):
        raise RuntimeError('Backend unavailable')
    monkeypatch.setattr('keyring.set_password', fail)
    response = hub.post('/api/connections', json=connection(api_key='private-key'))
    assert response.status_code == 400
    assert 'private-key' not in response.text
    assert not hub.store.settings()['api_connections']


def test_saved_page_keeps_connection_name_after_removal(hub):
    name = add(hub, requires_key=False)
    preferences = hub.store.settings() | {'provider': name}
    job = hub.store.create_job({'kind': 'import', 'preferences': preferences})
    page = hub.store.artifact_dir(job['id']) / 'page.html'
    hub.store.atomic_write(page, b'<html><body>Saved page</body></html>')
    generation = hub.store.publish_generation(job['id'], {'page_path': page, 'title': 'Saved custom page'})
    assert hub.delete('/api/connections/' + name).status_code == 200
    assert hub.store.get_generation(generation['id'])['metadata']['provider_name'] == 'My custom provider'
    assert hub.get('/api/generations/' + generation['id'] + '/export').status_code == 200
