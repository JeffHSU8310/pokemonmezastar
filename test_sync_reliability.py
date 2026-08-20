import base64
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, call, patch

import collection_manager
import github_sync
import qr_manager


def response(status_code, payload):
    result = Mock()
    result.status_code = status_code
    result.json.return_value = payload
    result.text = json.dumps(payload)
    return result


class TestSyncReliability(unittest.TestCase):
    def test_local_data_writers_replace_files_atomically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            collection_path = os.path.join(temp_dir, "collection.json")
            trainers_path = os.path.join(temp_dir, "trainers.json")
            with patch.object(collection_manager, "COLLECTION_FILE", collection_path), \
                 patch.object(collection_manager, "DATA_DIR", temp_dir), \
                 patch.object(collection_manager, "normalize_collection_ids", side_effect=lambda ids: ids), \
                 patch.object(qr_manager, "TRAINERS_FILE", trainers_path), \
                 patch.object(qr_manager, "DATA_DIR", temp_dir):
                self.assertTrue(collection_manager.save_user_collection_ids({"B", "A"}))
                self.assertTrue(qr_manager.save_trainers([{"id": "T1"}]))
            with open(collection_path, encoding="utf-8") as f:
                self.assertEqual(json.load(f), ["A", "B"])
            with open(trainers_path, encoding="utf-8") as f:
                self.assertEqual(json.load(f), [{"id": "T1"}])
            self.assertFalse(any(".tmp." in name for name in os.listdir(temp_dir)))

    def test_empty_collection_is_valid_for_overwrite(self):
        with patch.object(collection_manager, "load_cards", return_value=[]), \
             patch.object(collection_manager, "load_user_collection_ids", return_value={"old"}), \
             patch.object(collection_manager, "save_user_collection_ids", return_value=True) as save:
            ok, _, ids = collection_manager.import_collection_from_json("[]", mode="overwrite")
        self.assertTrue(ok)
        self.assertEqual(ids, set())
        save.assert_called_once_with(set())

    def test_download_uses_one_immutable_commit_for_both_files(self):
        collection = "[]"
        trainers = "[]"
        with patch.object(github_sync, "_get_branch_head", return_value=(True, "commit123", "")), \
             patch.object(github_sync, "_pull_file_at_ref", side_effect=[
                 (True, collection, github_sync._git_blob_sha(collection), ""),
                 (True, trainers, github_sync._git_blob_sha(trainers), "")
             ]) as pull:
            ok, got_collection, got_trainers, commit_sha, _ = github_sync.pull_all_user_data_from_github("token")
        self.assertTrue(ok)
        self.assertEqual((got_collection, got_trainers, commit_sha), (collection, trainers, "commit123"))
        self.assertEqual(pull.call_args_list, [
            call("data/my_collection.json", "commit123", "token"),
            call("data/trainers.json", "commit123", "token")
        ])

    def test_atomic_upload_creates_one_commit_and_reads_back_every_file(self):
        files = {"data/my_collection.json": "[]", "data/trainers.json": "[]"}
        blob_sha = github_sync._git_blob_sha("[]")
        get_responses = [response(200, {"tree": {"sha": "tree0"}})]
        post_responses = [
            response(201, {"sha": blob_sha}),
            response(201, {"sha": blob_sha}),
            response(201, {"sha": "tree1"}),
            response(201, {"sha": "commit1"})
        ]
        with patch.object(github_sync, "_get_branch_head", return_value=(True, "parent1", "")), \
             patch.object(github_sync.requests, "get", side_effect=get_responses), \
             patch.object(github_sync.requests, "post", side_effect=post_responses) as post_request, \
             patch.object(github_sync.requests, "patch", return_value=response(200, {})) as patch_request, \
             patch.object(github_sync, "_pull_file_at_ref", side_effect=[
                 (True, "[]", blob_sha, ""),
                 (True, "[]", blob_sha, "")
             ]) as pull:
            ok, commit_sha, error = github_sync._commit_files_atomically(files, "sync test", "token")
        self.assertTrue(ok, error)
        self.assertEqual(commit_sha, "commit1")
        self.assertEqual(post_request.call_count, 4)
        self.assertEqual(patch_request.call_count, 1)
        self.assertEqual(pull.call_count, 2)

    def test_download_rejects_content_when_blob_sha_does_not_match(self):
        content = "[]"
        payload = {
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "sha": "wrong"
        }
        with patch.object(github_sync.requests, "get", return_value=response(200, payload)):
            ok, _, _, error = github_sync._pull_file_at_ref("data/my_collection.json", "commit1", "token")
        self.assertFalse(ok)
        self.assertIn("SHA", error)

    def test_local_restore_rolls_back_if_second_file_fails(self):
        with patch.object(collection_manager, "load_user_collection_ids", return_value={"old"}), \
             patch.object(qr_manager, "load_trainers", return_value=[{"id": "old"}]), \
             patch.object(collection_manager, "save_user_collection_ids", side_effect=[True, True]) as save_collection, \
             patch.object(qr_manager, "save_trainers", side_effect=[False, True]) as save_trainers:
            ok, _, _, message = github_sync.restore_user_data_snapshot_locally(
                '["new"]', '[{"id":"new"}]'
            )
        self.assertFalse(ok)
        self.assertIn("已還原", message)
        self.assertEqual(save_collection.call_args_list, [call({"new"}), call({"old"})])
        self.assertEqual(save_trainers.call_args_list, [call([{"id": "new"}]), call([{"id": "old"}])])


if __name__ == "__main__":
    unittest.main()
