class TestCreateNote:
    def test_create_note(self, client, vault_dir):
        resp = client.post(
            "/api/notes",
            json={
                "path": "Inbox/new-note.md",
                "content": "# New Note\n\nCreated via API.",
                "metadata": {"tags": ["api"], "source": "test"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert data["path"] == "Inbox/new-note.md"
        assert (vault_dir / "Inbox" / "new-note.md").exists()

    def test_create_note_minimal(self, client, vault_dir):
        resp = client.post(
            "/api/notes",
            json={"path": "bare.md", "content": "Just content"},
        )
        assert resp.status_code == 200
        assert (vault_dir / "bare.md").exists()


class TestGetNote:
    def test_get_existing_note(self, client, sample_note):
        resp = client.get(f"/api/notes/{sample_note}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Note"
        assert "testing" in data["tags"]

    def test_get_missing_note_404(self, client):
        resp = client.get("/api/notes/nonexistent.md")
        assert resp.status_code == 404


class TestDeleteNote:
    def test_delete_existing(self, client, vault_dir, sample_note):
        resp = client.delete(f"/api/notes/{sample_note}")
        assert resp.status_code == 200
        assert not (vault_dir / sample_note).exists()

    def test_delete_missing_404(self, client):
        resp = client.delete("/api/notes/nonexistent.md")
        assert resp.status_code == 404


class TestSearch:
    def test_search_returns_results(self, client, mock_es):
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {"path": "note.md", "title": "Note", "tags": []},
                        "_score": 1.5,
                    }
                ]
            }
        }

        resp = client.post("/api/notes/search", json={"query": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["path"] == "note.md"

    def test_semantic_search(self, client, mock_es):
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {"path": "s.md", "title": "Semantic"},
                        "_score": 0.95,
                    }
                ]
            }
        }

        resp = client.post("/api/notes/semantic-search", json={"query": "meaning"})
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 1
