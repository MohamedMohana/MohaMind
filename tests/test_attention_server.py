from datetime import timedelta

import pytest

from moha_mind.mcp_servers.attention.server import AttentionServer
from moha_mind.utils.timezone import now_ksa


class TestAttentionServer:
    @pytest.mark.asyncio
    async def test_attention_radar_combines_signals(self, tmp_memory):
        tomorrow = (now_ksa() + timedelta(days=1)).replace(tzinfo=None)
        tomorrow = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        old_contact = (now_ksa() - timedelta(days=90)).strftime("%Y-%m-%d")
        tmp_memory.write(
            "tasks",
            f"# Tasks\n\n## Active\n- [ ] Submit launch post [HIGH] due:{tomorrow_str}\n",
        )
        tmp_memory.add_reminder("Join standup", remind_at=f"{tomorrow_str} 08:30", event_at=f"{tomorrow_str} 09:00")
        tmp_memory.write(
            "occasions",
            f"# Important Occasions\n\n## Birthdays\n- Sara birthday: 1990-{tomorrow_str[5:]}\n",
        )
        tmp_memory.write(
            "relationships",
            f"### Ahmed\n- Last contacted: {old_contact}\n- Contact frequency: monthly\n",
        )

        server = AttentionServer(tmp_memory)
        radar = await server._get_attention_radar(days_ahead=30, limit=8)

        assert "Attention Radar" in radar
        assert "Submit launch post" in radar
        assert "Join standup" in radar
        assert "Sara birthday" in radar
        assert "Ahmed" in radar

    @pytest.mark.asyncio
    async def test_attention_radar_calm_when_empty(self, tmp_memory):
        server = AttentionServer(tmp_memory)
        radar = await server._get_attention_radar()

        assert "calm" in radar.lower()
