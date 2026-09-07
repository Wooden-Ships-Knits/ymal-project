export default function BlockChip({ block, enabled = true, slots }) {
  return (
    <span className={`chip ${enabled ? '' : 'is-off'}`} title={block.description}>
      {block.label}
      {enabled && slots ? ` · ${slots}` : ''}
    </span>
  )
}
