"""API tests for the Flask application in app.py."""

import pytest


class TestGeneral:
    def test_index_lists_endpoints(self, client):
        response = client.get("/")
        assert response.status_code == 200
        body = response.get_json()
        assert body["app"] == "ACEest Fitness & Gym"
        assert "GET /health" in body["endpoints"]

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"

    def test_unknown_route_returns_json_404(self, client):
        response = client.get("/does-not-exist")
        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_wrong_method_returns_405(self, client):
        assert client.delete("/programs").status_code == 405


class TestLogin:
    def test_default_admin_can_login(self, client):
        response = client.post("/login", json={"username": "admin", "password": "admin"})
        assert response.status_code == 200
        assert response.get_json() == {"username": "admin", "role": "Admin"}

    @pytest.mark.parametrize(
        "creds", [{"username": "admin", "password": "wrong"}, {"username": "ghost", "password": "x"}]
    )
    def test_invalid_credentials(self, client, creds):
        assert client.post("/login", json=creds).status_code == 401

    def test_missing_fields(self, client):
        assert client.post("/login", json={"username": "admin"}).status_code == 400

    def test_non_json_body(self, client):
        assert client.post("/login", data="not json").status_code == 400

    def test_admin_password_from_config(self, tmp_path):
        from app import create_app

        app = create_app({"DATABASE": str(tmp_path / "a.db"), "ADMIN_PASSWORD": "s3cret"})
        c = app.test_client()
        assert c.post("/login", json={"username": "admin", "password": "s3cret"}).status_code == 200
        assert c.post("/login", json={"username": "admin", "password": "admin"}).status_code == 401


class TestPrograms:
    def test_list_programs(self, client):
        codes = {p["code"] for p in client.get("/programs").get_json()}
        assert codes == {"FL", "MG", "BG"}

    def test_get_program_details(self, client):
        body = client.get("/programs/mg").get_json()
        assert body["code"] == "MG"
        assert body["name"] == "Muscle Gain"
        assert body["workout"] and body["diet"]

    def test_unknown_program(self, client):
        assert client.get("/programs/XX").status_code == 404


class TestClients:
    def test_create_client_calculates_calories(self, sample_client):
        assert sample_client["id"] == 1
        assert sample_client["calories"] == 80 * 22
        assert sample_client["program"] == "FL"
        assert sample_client["membership_status"] == "Active"

    def test_create_minimal_client(self, client):
        response = client.post("/clients", json={"name": "Priya"})
        assert response.status_code == 201
        body = response.get_json()
        assert body["calories"] is None
        assert body["membership_status"] == "None"

    def test_duplicate_name_conflict(self, client, sample_client):
        assert client.post("/clients", json={"name": "Arun"}).status_code == 409

    @pytest.mark.parametrize(
        "payload, message",
        [
            ({}, "'name' is required"),
            ({"name": "  "}, "'name' is required"),
            ({"name": "A", "age": "old"}, "'age' must be a number"),
            ({"name": "A", "age": 25.5}, "'age' must be a whole number"),
            ({"name": "A", "age": 0}, "'age' must be between"),
            ({"name": "A", "weight": True}, "'weight' must be a number"),
            ({"name": "A", "program": "XX"}, "'program' must be one of"),
            ({"name": "A", "target_adherence": 150}, "'target_adherence' must be between"),
            ({"name": "A", "membership_end": "31-12-2026"}, "YYYY-MM-DD"),
            ({"name": 123}, "'name' must be a string"),
        ],
    )
    def test_create_client_validation(self, client, payload, message):
        response = client.post("/clients", json=payload)
        assert response.status_code == 400
        assert message in response.get_json()["error"]

    def test_list_clients_sorted_by_name(self, client):
        for name in ["Zara", "Bala", "Meena"]:
            client.post("/clients", json={"name": name})
        names = [c["name"] for c in client.get("/clients").get_json()]
        assert names == ["Bala", "Meena", "Zara"]

    def test_get_client(self, client, sample_client):
        body = client.get(f"/clients/{sample_client['id']}").get_json()
        assert body["name"] == "Arun"

    def test_get_missing_client(self, client):
        assert client.get("/clients/999").status_code == 404

    def test_update_client_recalculates_calories(self, client, sample_client):
        response = client.put("/clients/1", json={"program": "MG", "weight": 90})
        assert response.status_code == 200
        body = response.get_json()
        assert body["program"] == "MG"
        assert body["calories"] == 90 * 35
        assert body["age"] == 28  # untouched fields are kept

    def test_update_with_invalid_data(self, client, sample_client):
        assert client.put("/clients/1", json={"weight": -1}).status_code == 400

    def test_update_missing_client(self, client):
        assert client.put("/clients/999", json={"age": 30}).status_code == 404

    def test_delete_client_removes_related_data(self, client, sample_client):
        client.post("/clients/1/progress", json={"week": "W1", "adherence": 80})
        assert client.delete("/clients/1").status_code == 204
        assert client.get("/clients/1").status_code == 404
        assert client.get("/clients/1/progress").status_code == 404

    def test_delete_missing_client(self, client):
        assert client.delete("/clients/999").status_code == 404

    def test_expired_membership(self, client):
        client.post("/clients", json={"name": "Old", "membership_end": "2000-01-01"})
        body = client.get("/clients/1/membership").get_json()
        assert body == {"client_id": 1, "status": "Expired", "renewal_date": "2000-01-01"}

    def test_membership_missing_client(self, client):
        assert client.get("/clients/999/membership").status_code == 404


class TestBmiEndpoint:
    def test_bmi(self, client, sample_client):
        body = client.get("/clients/1/bmi").get_json()
        assert body["bmi"] == 26.1
        assert body["category"] == "Overweight"

    def test_bmi_needs_height_and_weight(self, client):
        client.post("/clients", json={"name": "NoData"})
        assert client.get("/clients/1/bmi").status_code == 400

    def test_bmi_missing_client(self, client):
        assert client.get("/clients/999/bmi").status_code == 404


class TestProgramGeneration:
    def test_generate_for_existing_program(self, client, sample_client):
        response = client.post("/clients/1/program")
        assert response.status_code == 200
        body = response.get_json()
        assert body["program"] == "FL"
        assert body["template"] in ["Full Body HIIT", "Circuit Training", "Cardio + Weights"]

    def test_generate_with_new_program_updates_client(self, client, sample_client):
        client.post("/clients/1/program", json={"program": "MG"})
        updated = client.get("/clients/1").get_json()
        assert updated["program"] == "MG"
        assert updated["calories"] == 80 * 35

    def test_generate_random_program_for_new_client(self, client):
        client.post("/clients", json={"name": "New"})
        body = client.post("/clients/1/program").get_json()
        assert body["program"] in {"FL", "MG", "BG"}

    def test_generate_invalid_program(self, client, sample_client):
        assert client.post("/clients/1/program", json={"program": "XX"}).status_code == 400

    def test_generate_missing_client(self, client):
        assert client.post("/clients/999/program").status_code == 404


class TestProgress:
    def test_add_and_list_progress(self, client, sample_client):
        client.post("/clients/1/progress", json={"week": "W1", "adherence": 80})
        response = client.post("/clients/1/progress", json={"week": "W2", "adherence": 95})
        assert response.status_code == 201
        body = client.get("/clients/1/progress").get_json()
        assert [e["week"] for e in body["entries"]] == ["W1", "W2"]
        assert body["average_adherence"] == 87.5

    def test_empty_progress(self, client, sample_client):
        body = client.get("/clients/1/progress").get_json()
        assert body["entries"] == [] and body["average_adherence"] == 0.0

    @pytest.mark.parametrize(
        "payload",
        [
            {"adherence": 80},
            {"week": "W1"},
            {"week": "W1", "adherence": 101},
            {"week": "W1", "adherence": -1},
        ],
    )
    def test_progress_validation(self, client, sample_client, payload):
        assert client.post("/clients/1/progress", json=payload).status_code == 400

    def test_progress_missing_client(self, client):
        assert client.post("/clients/999/progress", json={"week": "W1", "adherence": 50}).status_code == 404


class TestWorkouts:
    def test_add_workout_with_exercises(self, client, sample_client):
        response = client.post(
            "/clients/1/workouts",
            json={
                "date": "2026-10-01",
                "workout_type": "Strength",
                "duration_min": 60,
                "notes": "Leg day",
                "exercises": [
                    {"name": "Back Squat", "sets": 5, "reps": 5, "weight": 100},
                    {"name": "Lunges", "sets": 3, "reps": 12},
                ],
            },
        )
        assert response.status_code == 201
        body = response.get_json()
        assert body["workout_type"] == "Strength"
        assert [e["name"] for e in body["exercises"]] == ["Back Squat", "Lunges"]

    def test_workout_date_defaults_to_today(self, client, sample_client):
        from datetime import date

        body = client.post(
            "/clients/1/workouts", json={"workout_type": "Cardio", "duration_min": 30}
        ).get_json()
        assert body["date"] == date.today().isoformat()

    def test_list_workouts_newest_first(self, client, sample_client):
        for day in ["2026-09-01", "2026-09-15", "2026-09-08"]:
            client.post(
                "/clients/1/workouts",
                json={"date": day, "workout_type": "Mobility", "duration_min": 20},
            )
        dates = [w["date"] for w in client.get("/clients/1/workouts").get_json()]
        assert dates == ["2026-09-15", "2026-09-08", "2026-09-01"]

    @pytest.mark.parametrize(
        "payload",
        [
            {"duration_min": 30},
            {"workout_type": "Yoga", "duration_min": 30},
            {"workout_type": "Cardio"},
            {"workout_type": "Cardio", "duration_min": 0},
            {"workout_type": "Cardio", "duration_min": 30, "date": "yesterday"},
            {"workout_type": "Cardio", "duration_min": 30, "exercises": "squats"},
            {"workout_type": "Cardio", "duration_min": 30, "exercises": [{"sets": 3}]},
            {"workout_type": "Cardio", "duration_min": 30, "exercises": ["squats"]},
        ],
    )
    def test_workout_validation(self, client, sample_client, payload):
        assert client.post("/clients/1/workouts", json=payload).status_code == 400

    def test_invalid_workout_is_not_saved(self, client, sample_client):
        client.post(
            "/clients/1/workouts",
            json={"workout_type": "Cardio", "duration_min": 30, "exercises": [{"sets": 3}]},
        )
        assert client.get("/clients/1/workouts").get_json() == []

    def test_workouts_missing_client(self, client):
        assert client.get("/clients/999/workouts").status_code == 404


class TestMetrics:
    def test_add_and_list_metrics(self, client, sample_client):
        response = client.post(
            "/clients/1/metrics", json={"date": "2026-09-01", "weight": 80, "waist": 90, "bodyfat": 22}
        )
        assert response.status_code == 201
        client.post("/clients/1/metrics", json={"date": "2026-09-08", "weight": 79})
        rows = client.get("/clients/1/metrics").get_json()
        assert [r["weight"] for r in rows] == [80.0, 79.0]
        assert rows[1]["waist"] is None

    def test_metrics_need_at_least_one_value(self, client, sample_client):
        assert client.post("/clients/1/metrics", json={"date": "2026-09-01"}).status_code == 400

    def test_metrics_out_of_range(self, client, sample_client):
        assert client.post("/clients/1/metrics", json={"bodyfat": 90}).status_code == 400

    def test_metrics_missing_client(self, client):
        assert client.get("/clients/999/metrics").status_code == 404
