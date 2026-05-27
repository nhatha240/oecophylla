<script lang="ts">
  import Avatar from './Avatar.svelte';
  import Icon from './Icon.svelte';
  import type { Author } from '../data';

  export let author: Author;
  export let time = '';
  export let body = '';
</script>

<div class="comment">
  <Avatar {author} size="s40" showVerified />
  <div style="flex: 1">
    <div class="c-meta"><span class="name">{author.name}</span><span class="time">{time}</span></div>
    <div class="c-body">{body}</div>
    <div class="c-acts"><button><Icon name="Heart" size={12} style="vertical-align: -2px; margin-right: 4px" /> 8</button><button>Trả lời</button><button>Báo cáo</button></div>
  </div>
</div>
