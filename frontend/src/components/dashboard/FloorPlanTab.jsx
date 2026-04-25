/**
 * FloorPlanTab — Visual floor plan / table management for restaurants.
 * Drag-and-drop table layout with real-time status (available/occupied/reserved).
 */
import { useState, useRef, useMemo, useCallback, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '../Toast';
import {
  getFloorPlan,
  saveFloorPlan,
  getTableStatuses,
  updateTableStatus,
} from '../../services/api';
import './FloorPlanTab.css';

const TABLE_SHAPES = [
  { id: 'round-2', label: 'Round (2)', shape: 'round', seats: 2, w: 60, h: 60 },
  { id: 'round-4', label: 'Round (4)', shape: 'round', seats: 4, w: 72, h: 72 },
  { id: 'round-6', label: 'Round (6)', shape: 'round', seats: 6, w: 88, h: 88 },
  { id: 'rect-2', label: 'Square (2)', shape: 'rect', seats: 2, w: 60, h: 60 },
  { id: 'rect-4', label: 'Rect (4)', shape: 'rect', seats: 4, w: 100, h: 60 },
  { id: 'rect-6', label: 'Rect (6)', shape: 'rect', seats: 6, w: 130, h: 60 },
  { id: 'rect-8', label: 'Long (8)', shape: 'rect', seats: 8, w: 170, h: 60 },
  { id: 'bar-4', label: 'Bar (4)', shape: 'bar', seats: 4, w: 120, h: 36 },
];

const STATUS_COLORS = {
  available: '#10b981',
  occupied: '#ef4444',
  reserved: '#f59e0b',
  cleaning: '#8b5cf6',
};

const STATUS_LABELS = {
  available: 'Available',
  occupied: 'Occupied',
  reserved: 'Reserved',
  cleaning: 'Cleaning',
};

function FloorPlanTab() {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const canvasRef = useRef(null);

  const [isEditMode, setIsEditMode] = useState(false);
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState(null);
  const [dragging, setDragging] = useState(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [floorName, setFloorName] = useState('Main Floor');
  const [statusPopover, setStatusPopover] = useState(null);
  const [originalTables, setOriginalTables] = useState([]);

  // Fetch saved floor plan
  const { data: floorData, isLoading } = useQuery({
    queryKey: ['floor-plan'],
    queryFn: async () => {
      try { const r = await getFloorPlan(); return r.data; }
      catch { return { tables: [], floor_name: 'Main Floor' }; }
    },
  });

  // Fetch live table statuses
  const { data: statusData } = useQuery({
    queryKey: ['table-statuses'],
    queryFn: async () => {
      try { const r = await getTableStatuses(); return r.data; }
      catch { return { statuses: {} }; }
    },
    refetchInterval: 30000,
  });

  const tableStatuses = statusData?.statuses || {};

  useEffect(() => {
    if (floorData?.tables) {
      setTables(floorData.tables);
      setFloorName(floorData.floor_name || 'Main Floor');
    }
  }, [floorData]);

  const saveMutation = useMutation({
    mutationFn: (data) => saveFloorPlan(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['floor-plan'] });
      addToast('Floor plan saved', 'success');
      setIsEditMode(false);
    },
    onError: () => addToast('Failed to save floor plan', 'error'),
  });

  const statusMutation = useMutation({
    mutationFn: ({ tableId, status, guestName, partySize }) =>
      updateTableStatus(tableId, status, guestName, partySize),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['table-statuses'] });
      setStatusPopover(null);
    },
    onError: () => addToast('Failed to update table', 'error'),
  });

  const handleSave = () => {
    saveMutation.mutate({ tables, floor_name: floorName });
  };

  const addTable = (template) => {
    const id = `table-${Date.now()}`;
    const num = tables.length + 1;
    setTables(prev => [...prev, {
      id,
      name: `T${num}`,
      shape: template.shape,
      seats: template.seats,
      w: template.w,
      h: template.h,
      x: 40 + (tables.length % 4) * 120,
      y: 40 + Math.floor(tables.length / 4) * 100,
      area: 'Indoor',
    }]);
  };

  const removeTable = (id) => {
    setTables(prev => prev.filter(t => t.id !== id));
    if (selectedTable === id) setSelectedTable(null);
  };

  const handleMouseDown = (e, table) => {
    if (!isEditMode) {
      setStatusPopover(statusPopover === table.id ? null : table.id);
      return;
    }
    e.preventDefault();
    const rect = canvasRef.current.getBoundingClientRect();
    setDragging(table.id);
    setDragOffset({
      x: e.clientX - rect.left - table.x,
      y: e.clientY - rect.top - table.y,
    });
    setSelectedTable(table.id);
  };

  const handleMouseMove = useCallback((e) => {
    if (!dragging || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width - 40, e.clientX - rect.left - dragOffset.x));
    const y = Math.max(0, Math.min(rect.height - 40, e.clientY - rect.top - dragOffset.y));
    setTables(prev => prev.map(t => t.id === dragging ? { ...t, x, y } : t));
  }, [dragging, dragOffset]);

  const handleMouseUp = useCallback(() => {
    setDragging(null);
  }, []);

  useEffect(() => {
    if (dragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [dragging, handleMouseMove, handleMouseUp]);

  // Touch support
  const handleTouchStart = (e, table) => {
    if (!isEditMode) {
      setStatusPopover(statusPopover === table.id ? null : table.id);
      return;
    }
    const touch = e.touches[0];
    const rect = canvasRef.current.getBoundingClientRect();
    setDragging(table.id);
    setDragOffset({
      x: touch.clientX - rect.left - table.x,
      y: touch.clientY - rect.top - table.y,
    });
    setSelectedTable(table.id);
  };

  const handleTouchMove = useCallback((e) => {
    if (!dragging || !canvasRef.current) return;
    e.preventDefault();
    const touch = e.touches[0];
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width - 40, touch.clientX - rect.left - dragOffset.x));
    const y = Math.max(0, Math.min(rect.height - 40, touch.clientY - rect.top - dragOffset.y));
    setTables(prev => prev.map(t => t.id === dragging ? { ...t, x, y } : t));
  }, [dragging, dragOffset]);

  useEffect(() => {
    if (dragging) {
      window.addEventListener('touchmove', handleTouchMove, { passive: false });
      window.addEventListener('touchend', handleMouseUp);
      return () => {
        window.removeEventListener('touchmove', handleTouchMove);
        window.removeEventListener('touchend', handleMouseUp);
      };
    }
  }, [dragging, handleTouchMove, handleMouseUp]);

  const stats = useMemo(() => {
    const total = tables.length;
    const totalSeats = tables.reduce((s, t) => s + t.seats, 0);
    let available = 0, occupied = 0, reserved = 0;
    tables.forEach(t => {
      const st = tableStatuses[t.id]?.status || 'available';
      if (st === 'available') available++;
      else if (st === 'occupied') occupied++;
      else if (st === 'reserved') reserved++;
    });
    return { total, totalSeats, available, occupied, reserved };
  }, [tables, tableStatuses]);

  if (isLoading) return <div className="fp-loading"><div className="fp-spinner"></div></div>;

  return (
    <div className="floor-plan-tab">
      <div className="fp-header">
        <div className="fp-header-left">
          <h2><i className="fas fa-map"></i> Floor Plan</h2>
          <p className="fp-subtitle">{stats.total} tables · {stats.totalSeats} seats</p>
        </div>
        <div className="fp-header-right">
          {isEditMode ? (
            <>
              <button className="btn-secondary btn-sm" onClick={() => { setTables(originalTables); setIsEditMode(false); setSelectedTable(null); }}>Cancel</button>
              <button className="btn-primary btn-sm" onClick={handleSave} disabled={saveMutation.isPending}>
                {saveMutation.isPending ? 'Saving...' : 'Save Layout'}
              </button>
            </>
          ) : (
            <button className="btn-secondary btn-sm" onClick={() => { setOriginalTables([...tables]); setIsEditMode(true); }}>
              <i className="fas fa-pencil-alt"></i> Edit Layout
            </button>
          )}
        </div>
      </div>

      {/* Stats strip */}
      {tables.length > 0 && !isEditMode && (
        <div className="fp-stats">
          <span className="fp-stat">
            <span className="fp-stat-dot" style={{ background: STATUS_COLORS.available }}></span>
            {stats.available} available
          </span>
          <span className="fp-stat">
            <span className="fp-stat-dot" style={{ background: STATUS_COLORS.occupied }}></span>
            {stats.occupied} occupied
          </span>
          <span className="fp-stat">
            <span className="fp-stat-dot" style={{ background: STATUS_COLORS.reserved }}></span>
            {stats.reserved} reserved
          </span>
        </div>
      )}

      {/* Edit mode: table palette */}
      {isEditMode && (
        <div className="fp-palette">
          <span className="fp-palette-label">Add table:</span>
          <div className="fp-palette-items">
            {TABLE_SHAPES.map(t => (
              <button key={t.id} className="fp-palette-btn" onClick={() => addTable(t)}>
                <span className={`fp-shape-icon fp-shape-${t.shape}`}></span>
                <span>{t.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Canvas */}
      <div
        className={`fp-canvas ${isEditMode ? 'edit-mode' : ''}`}
        ref={canvasRef}
        onClick={(e) => { if (e.target === canvasRef.current) { setSelectedTable(null); setStatusPopover(null); } }}
      >
        {tables.length === 0 ? (
          <div className="fp-empty">
            <i className="fas fa-chair"></i>
            <h4>No tables yet</h4>
            <p>Click "Edit Layout" to start adding tables to your floor plan.</p>
          </div>
        ) : (
          tables.map(table => {
            const status = tableStatuses[table.id]?.status || 'available';
            const guest = tableStatuses[table.id]?.guest_name;
            const party = tableStatuses[table.id]?.party_size;
            const color = STATUS_COLORS[status];
            const isSelected = selectedTable === table.id;

            return (
              <div
                key={table.id}
                className={`fp-table fp-table-${table.shape} ${isSelected ? 'selected' : ''} ${dragging === table.id ? 'dragging' : ''}`}
                style={{
                  left: table.x,
                  top: table.y,
                  width: table.w,
                  height: table.h,
                  borderColor: color,
                  background: `${color}18`,
                  cursor: isEditMode ? 'grab' : 'pointer',
                }}
                onMouseDown={(e) => handleMouseDown(e, table)}
                onTouchStart={(e) => handleTouchStart(e, table)}
              >
                <span className="fp-table-name">{table.name}</span>
                <span className="fp-table-seats">{table.seats}</span>
                {!isEditMode && guest && (
                  <span className="fp-table-guest">{guest}{party ? ` (${party})` : ''}</span>
                )}
                {isEditMode && isSelected && (
                  <button className="fp-table-remove" onClick={(e) => { e.stopPropagation(); removeTable(table.id); }}>
                    <i className="fas fa-times"></i>
                  </button>
                )}

                {/* Status popover */}
                {!isEditMode && statusPopover === table.id && (
                  <TableStatusPopover
                    table={table}
                    currentStatus={status}
                    currentGuest={guest}
                    currentParty={party}
                    onUpdate={(s, g, p) => statusMutation.mutate({ tableId: table.id, status: s, guestName: g, partySize: p })}
                    onClose={() => setStatusPopover(null)}
                  />
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Edit mode: selected table properties */}
      {isEditMode && selectedTable && (() => {
        const table = tables.find(t => t.id === selectedTable);
        if (!table) return null;
        return (
          <div className="fp-props">
            <h4>Table Properties</h4>
            <div className="fp-props-grid">
              <div className="fp-prop">
                <label>Name</label>
                <input
                  type="text"
                  value={table.name}
                  onChange={(e) => setTables(prev => prev.map(t => t.id === selectedTable ? { ...t, name: e.target.value } : t))}
                  placeholder="e.g., T1"
                />
              </div>
              <div className="fp-prop">
                <label>Seats</label>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={table.seats}
                  onChange={(e) => setTables(prev => prev.map(t => t.id === selectedTable ? { ...t, seats: parseInt(e.target.value) || 1 } : t))}
                />
              </div>
              <div className="fp-prop">
                <label>Area</label>
                <select
                  value={table.area || 'Indoor'}
                  onChange={(e) => setTables(prev => prev.map(t => t.id === selectedTable ? { ...t, area: e.target.value } : t))}
                >
                  <option>Indoor</option>
                  <option>Outdoor</option>
                  <option>Private Room</option>
                  <option>Bar</option>
                  <option>Terrace</option>
                </select>
              </div>
            </div>
            <button className="btn-danger btn-sm" onClick={() => removeTable(selectedTable)} style={{ marginTop: '0.5rem' }}>
              <i className="fas fa-trash"></i> Remove Table
            </button>
          </div>
        );
      })()}
    </div>
  );
}

function TableStatusPopover({ table, currentStatus, currentGuest, currentParty, onUpdate, onClose }) {
  const [guestName, setGuestName] = useState(currentGuest || '');
  const [partySize, setPartySize] = useState(currentParty || '');

  return (
    <div className="fp-popover" onClick={(e) => e.stopPropagation()}>
      <div className="fp-popover-header">
        <strong>{table.name}</strong> · {table.seats} seats
        <button className="fp-popover-close" onClick={onClose}><i className="fas fa-times"></i></button>
      </div>
      <div className="fp-popover-statuses">
        {Object.entries(STATUS_LABELS).map(([key, label]) => (
          <button
            key={key}
            className={`fp-status-btn ${currentStatus === key ? 'active' : ''}`}
            style={{ '--status-color': STATUS_COLORS[key] }}
            onClick={() => {
              const needsGuest = key === 'occupied' || key === 'reserved';
              onUpdate(key, needsGuest ? guestName : '', needsGuest ? partySize : '');
            }}
          >
            <span className="fp-status-dot" style={{ background: STATUS_COLORS[key] }}></span>
            {label}
          </button>
        ))}
      </div>
      {(currentStatus === 'occupied' || currentStatus === 'reserved') && (
        <div className="fp-popover-fields">
          <input
            type="text"
            placeholder="Guest name"
            value={guestName}
            onChange={(e) => setGuestName(e.target.value)}
            onBlur={() => onUpdate(currentStatus, guestName, partySize)}
          />
          <input
            type="number"
            placeholder="Party size"
            min="1"
            value={partySize}
            onChange={(e) => setPartySize(e.target.value)}
            onBlur={() => onUpdate(currentStatus, guestName, partySize)}
          />
        </div>
      )}
    </div>
  );
}

export default FloorPlanTab;
