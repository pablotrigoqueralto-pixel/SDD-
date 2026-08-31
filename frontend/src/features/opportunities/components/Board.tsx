import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { useQueryClient } from '@tanstack/react-query';
import { GripVertical } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { opportunityKeys } from '@/api/query-keys';
import { formatPrice } from '@/features/catalogue';
import { toast } from '@/hooks/use-toast';
import { toProblem } from '@/lib/problem';
import { useConflictStore } from '@/store/conflict.store';

import type { BoardRead, OpportunitySummaryRead } from '../api';
import { useCanWriteOpportunity } from '../hooks';
import { useMoveStage } from '../queries';
import { OpportunityCard } from './OpportunityCard';

interface BoardProps {
  board: BoardRead;
  onSelect: (opportunity: OpportunitySummaryRead) => void;
  /** Called when a card is dropped on the won / lost column. */
  onClose: (opportunity: OpportunitySummaryRead, kind: 'win' | 'lose') => void;
}

interface CloseZone {
  id: string;
  kind: 'win' | 'lose';
  label: string;
}

export function Board({ board, onSelect, onClose }: BoardProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const move = useMoveStage();
  const [pending, setPending] = useState<{ id: string; stageId: string } | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const cards = new Map<string, OpportunitySummaryRead>();
  for (const column of board.columns) {
    for (const item of column.items) cards.set(item.id, item);
  }
  const stageNames = new Map(board.pipeline.stages.map((stage) => [stage.id, stage.name_es]));
  const wonStage = board.pipeline.stages.find((stage) => stage.is_won);
  const lostStage = board.pipeline.stages.find((stage) => stage.is_lost);
  const closeZones: CloseZone[] = [
    ...(wonStage ? [{ id: `close-win`, kind: 'win' as const, label: wonStage.name_es }] : []),
    ...(lostStage ? [{ id: `close-lose`, kind: 'lose' as const, label: lostStage.name_es }] : []),
  ];

  const announcements: Announcements = {
    onDragStart: ({ active }) =>
      t('opportunities:board.cardLifted', { name: cards.get(String(active.id))?.name ?? '' }),
    onDragOver: () => undefined,
    onDragEnd: ({ active, over }) =>
      over
        ? t('opportunities:board.cardDropped', {
            name: cards.get(String(active.id))?.name ?? '',
            stage: stageNames.get(String(over.id)) ?? '',
          })
        : t('opportunities:board.cardCancelled'),
    onDragCancel: () => t('opportunities:board.cardCancelled'),
  };

  const columnOfCard = (cardId: string): string | undefined =>
    board.columns.find((column) => column.items.some((item) => item.id === cardId))?.stage.id;

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over) return;
    const card = cards.get(String(active.id));
    if (!card) return;
    const overId = String(over.id);
    const closeZone = closeZones.find((zone) => zone.id === overId);
    if (closeZone) {
      onClose(card, closeZone.kind);
      return;
    }
    const targetStage = stageNames.has(overId) ? overId : columnOfCard(overId);
    if (!targetStage || targetStage === card.stage_id) return;
    setPending({ id: card.id, stageId: targetStage });
    move
      .mutateAsync({
        id: card.id,
        accountId: card.account_id,
        version: card.version,
        stageId: targetStage,
      })
      .then(() => {
        toast({
          description: t('opportunities:moved', { stage: stageNames.get(targetStage) ?? '' }),
        });
      })
      .catch((error: unknown) => {
        const problem = toProblem(error);
        if (problem.code === 'conflict') {
          useConflictStore
            .getState()
            .show(() => queryClient.invalidateQueries({ queryKey: opportunityKeys.boards() }));
        } else {
          toast({ description: t('toasts.genericError'), variant: 'destructive' });
        }
      })
      .finally(() => {
        setPending(null);
      });
  };

  return (
    <DndContext sensors={sensors} accessibility={{ announcements }} onDragEnd={handleDragEnd}>
      <div
        role="region"
        aria-label={t('opportunities:title')}
        // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- axe requires scrollable regions to be keyboard reachable
        tabIndex={0}
        className="flex gap-3 overflow-x-auto pb-3"
        data-testid="board"
      >
        {board.columns.map((column) => (
          <BoardColumn
            key={column.stage.id}
            columnId={column.stage.id}
            title={column.stage.name_es}
            summary={t('opportunities:board.columnTotal', {
              count: column.count,
              amount: formatPrice(column.total_amount),
            })}
            hasMore={column.has_more}
          >
            {column.items.map((item) => {
              const moved = pending !== null && pending.id === item.id;
              return (
                <BoardCard
                  key={item.id}
                  opportunity={moved ? { ...item, stage_id: pending.stageId } : item}
                  dimmed={moved}
                  onSelect={onSelect}
                />
              );
            })}
          </BoardColumn>
        ))}
        <div className="flex w-32 shrink-0 flex-col gap-3">
          {closeZones.map((zone) => (
            <CloseColumn key={zone.id} zone={zone} />
          ))}
        </div>
      </div>
      <p className="text-sm text-muted-foreground">
        {t('opportunities:board.closedThisMonth', {
          won: board.closed_this_month.won_count,
          amount: formatPrice(board.closed_this_month.won_amount),
          lost: board.closed_this_month.lost_count,
        })}
      </p>
    </DndContext>
  );
}

interface BoardColumnProps {
  columnId: string;
  title: string;
  summary: string;
  hasMore: boolean;
  children: React.ReactNode;
}

function BoardColumn({ columnId, title, summary, hasMore, children }: BoardColumnProps) {
  const { t } = useTranslation();
  const { setNodeRef, isOver } = useDroppable({ id: columnId });
  return (
    <section
      ref={setNodeRef}
      aria-label={title}
      className={`flex min-w-44 flex-1 flex-col gap-2 rounded-lg border p-2 ${
        isOver ? 'border-primary bg-accent/40' : 'bg-muted/30'
      }`}
    >
      <header className="flex flex-wrap items-baseline justify-between gap-x-2 px-1">
        <h3 className="font-semibold">{title}</h3>
        <span className="text-sm tabular-nums text-muted-foreground">{summary}</span>
      </header>
      {children}
      {hasMore ? (
        <p className="px-1 text-xs text-muted-foreground">{t('opportunities:board.hasMore')}</p>
      ) : null}
    </section>
  );
}

function CloseColumn({ zone }: { zone: CloseZone }) {
  const { setNodeRef, isOver } = useDroppable({ id: zone.id });
  return (
    <div
      ref={setNodeRef}
      aria-label={zone.label}
      className={`flex flex-1 items-center justify-center rounded-lg border border-dashed p-2 text-sm font-medium ${
        isOver ? 'border-primary bg-accent/40' : 'text-muted-foreground'
      }`}
    >
      {zone.label}
    </div>
  );
}

interface BoardCardProps {
  opportunity: OpportunitySummaryRead;
  dimmed: boolean;
  onSelect: (opportunity: OpportunitySummaryRead) => void;
}

function BoardCard({ opportunity, dimmed, onSelect }: BoardCardProps) {
  const { t } = useTranslation();
  const canWrite = useCanWriteOpportunity(opportunity);
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, isDragging } =
    useDraggable({
      id: opportunity.id,
      disabled: !canWrite,
    });
  const style = transform
    ? { transform: `translate(${transform.x}px, ${transform.y}px)` }
    : undefined;
  // The drag activator is a sibling handle, never a wrapper around the card's own
  // button — nesting two interactive elements fails axe (nested-interactive).
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-stretch gap-1 ${isDragging || dimmed ? 'opacity-60' : ''}`}
    >
      <div className="min-w-0 flex-1">
        <OpportunityCard opportunity={opportunity} onSelect={onSelect} showAccount />
      </div>
      {canWrite ? (
        <button
          type="button"
          ref={setActivatorNodeRef}
          {...listeners}
          {...attributes}
          aria-label={t('opportunities:board.move', { name: opportunity.name })}
          className="flex w-6 shrink-0 cursor-grab touch-none items-center justify-center rounded-lg border text-muted-foreground hover:bg-muted"
        >
          <GripVertical className="size-4" aria-hidden="true" />
        </button>
      ) : null}
    </div>
  );
}
