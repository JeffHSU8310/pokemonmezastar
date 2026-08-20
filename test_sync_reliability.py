import base64
import json
import unittest
from unittest.mock import Mock, call, patch

import collection_manager
import github_sync


def response(status_code, payload):
    result = Mock()
    result.status_code = status_code
    result.json.return_value = payload
    result.text = json.dumps(payload)
    return result


class TestSyncReliability(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
