<script lang="ts">
  import AdminShell from '$lib/apple-glass/admin/AdminShell.svelte';
  import Icon from '$lib/apple-glass/components/Icon.svelte';
  import { mockReports, mockMetrics } from '$lib/mock/admin';

  let adminPage = 'overview';
</script>

<AdminShell page={adminPage} onNav={(page) => (adminPage = page)} onExit={() => history.back()}>
  <section class="admin-h">
    <div>
      <h2>Trung tâm quản trị</h2>
      <div class="sub">Bản admin mock hiện đang dùng dữ liệu cục bộ nhưng đã bám layout Apple Glass.</div>
    </div>
    <div class="admin-h-actions">
      <div class="date-range"><Icon name="Clock" size={14} /> 7 ngày qua</div>
    </div>
  </section>

  <section class="kpi-grid">
    {#each Object.entries(mockMetrics) as [k, v]}
      <div class="kpi">
        <div class="label">
          <span>{k}</span>
          <Icon name="ChartBar" size={14} />
        </div>
        <div class="value">{v}</div>
        <div class="delta up"><Icon name="TrendUp" size={12} /> cập nhật ổn định</div>
      </div>
    {/each}
  </section>

  <section class="chart-card">
    <div class="head">
      <div>
        <h4>Báo cáo đang chờ</h4>
        <div class="sub">Ưu tiên kiểm duyệt các bài có trạng thái nhạy cảm và cần xử lý sớm.</div>
      </div>
    </div>
    <table class="admin-table">
      <thead>
        <tr>
          <th>Lý do</th>
          <th>Post</th>
          <th>Trạng thái</th>
        </tr>
      </thead>
      <tbody>
        {#each mockReports as r (r.id)}
          <tr>
            <td>{r.reason}</td>
            <td>{r.post_id}</td>
            <td>{r.status}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>
</AdminShell>
