import shutil

import click
import pytest

from ape.cli import get_user_selected_account, network_option
from ape.exceptions import AccountsError

OUTPUT_FORMAT = "__TEST__{}__"


@pytest.fixture
def keyfile_swap_paths(config):
    return config.DATA_FOLDER / "accounts", config.DATA_FOLDER.parent / "temp_accounts"


@pytest.fixture
def no_keyfile_accounts(keyfile_swap_paths):
    src_path, dest_path = keyfile_swap_paths
    if dest_path.is_dir():
        shutil.rmtree(dest_path)

    if not src_path.is_dir() or not [x for x in src_path.iterdir()]:
        # No keyfile accounts already
        yield

    else:
        shutil.copytree(src_path, dest_path)
        shutil.rmtree(src_path)
        yield
        shutil.copytree(dest_path, src_path)
        shutil.rmtree(dest_path)


@pytest.fixture
def one_keyfile_account(keyfile_swap_paths, keyfile_account):
    src_path, dest_path = keyfile_swap_paths
    existing_keyfiles = [x for x in src_path.iterdir() if x.is_file()]
    if existing_keyfiles == [keyfile_account.keyfile_path]:
        # Already only has the 1 account
        yield keyfile_account

    else:
        if dest_path.exists():
            dest_path.unlink() if dest_path.is_file() else shutil.rmtree(dest_path)

        dest_path.mkdir()
        for keyfile in [x for x in existing_keyfiles if x != keyfile_account.keyfile_path]:
            shutil.copy(keyfile, dest_path / keyfile.name)
            keyfile.unlink()

        yield keyfile_account

        for file in dest_path.iterdir():
            shutil.copy(file, src_path / file.name)


@pytest.fixture
def network_cmd():
    @click.command()
    @network_option()
    def cmd(network):
        click.echo(OUTPUT_FORMAT.format(network))

    return cmd


def test_get_user_selected_account_no_accounts_found(no_keyfile_accounts):
    with pytest.raises(AccountsError) as err:
        get_user_selected_account()

    assert "No accounts found." in str(err.value)


def test_get_user_selected_account_one_account(runner, keyfile_account):
    # No input needed when only one account
    with runner.isolation():
        account = get_user_selected_account()

    assert account == keyfile_account


def test_get_user_selected_account_multiple_accounts_requires_input(
    runner, keyfile_account, second_keyfile_account
):
    with runner.isolation(input="0\n"):
        account = get_user_selected_account()

    assert account == keyfile_account


def test_get_user_selected_account_custom_prompt(runner, keyfile_account, second_keyfile_account):
    prompt = "THIS_IS_A_CUSTOM_PROMPT"
    with runner.isolation(input="0\n") as out_streams:
        get_user_selected_account(prompt)
        output = out_streams[0].getvalue().decode()

    assert prompt in output


def test_get_user_selected_account_specify_type(runner, one_keyfile_account):
    with runner.isolation():
        account = get_user_selected_account(account_type=type(one_keyfile_account))

    assert account == one_keyfile_account


def test_get_user_selected_account_unknown_type(runner, keyfile_account):
    with pytest.raises(AccountsError) as err:
        get_user_selected_account(account_type=str)  # type: ignore

    assert "Cannot return accounts with type '<class 'str'>'" in str(err.value)


def test_network_option_default(runner, network_cmd):
    result = runner.invoke(network_cmd)
    assert result.exit_code == 0, result.output
    assert OUTPUT_FORMAT.format("ethereum") in result.output


def test_network_option_specified(runner, network_cmd):
    result = runner.invoke(network_cmd, ["--network", "ethereum:local:test"])
    assert result.exit_code == 0, result.output
    assert OUTPUT_FORMAT.format("ethereum:local:test") in result.output


def test_network_option_unknown(runner, network_cmd):
    result = runner.invoke(network_cmd, ["--network", "UNKNOWN"])
    assert result.exit_code != 0, result.output
    assert "Invalid value for '--network'" in result.output


@pytest.mark.parametrize(
    "network_input",
    (
        "something:else:https://127.0.0.1:4545",
        "something:else:https://127.0.0.1",
        "something:else:http://127.0.0.1:4545",
        "something:else:http://127.0.0.1",
        "something:else:http://foo.bar",
        "something:else:https://foo.bar:8000",
        ":else:https://foo.bar:8000",
        "::https://foo.bar:8000",
        "https://foo.bar:8000",
    ),
)
def test_network_option_adhoc(runner, network_cmd, network_input):
    result = runner.invoke(network_cmd, ["--network", network_input])
    assert result.exit_code == 0, result.output
    assert OUTPUT_FORMAT.format(network_input) in result.output
