import {request} from '../api.js';
import {actionForm} from '../controls.js';
import {el} from '../dom.js';
import {dataView, status, titleBlock} from '../widgets.js';

const TRACK_COLUMNS = [
  {name: 'code', label: '编号'},
  {name: 'venue', label: '场地'},
  {name: 'clock', label: '时钟来源'},
  {name: 'metronome', label: '计拍器'},
  {name: 'measured_at', label: '测量时间'},
  {name: 'timings', label: '原始拍点'},
  {name: 'converted_timings', label: '换算拍点（原钟口径）'},
  {name: 'calibration', label: '认用标定'},
  {name: 'shift', label: '总偏移秒'},
  {name: 'locked', label: '模板已见证'},
];

const CALIBRATION_COLUMNS = [
  {name: 'code', label: '标定编号'},
  {name: 'metronome', label: '计拍器'},
  {name: 'valid_from', label: '时段起'},
  {name: 'valid_to', label: '时段止'},
  {name: 'scale', label: '时钟比例'},
  {name: 'offset', label: '时钟偏移'},
  {name: 'max_error', label: '检验最大误差/秒'},
  {name: 'enabled', label: '是否启用'},
  {name: 'note', label: '收存说明'},
];

const trackActions = [
  {
    name: 'record_track',
    label: '登记试投节奏',
    path: '/cue_tracks/record-track',
    fields: [
      {name: 'code', label: '素材号', kind: 'text', initial: 'CUE-FINAL'},
      {name: 'venue', label: '场地号', kind: 'text', initial: 'HALL-A'},
      {name: 'timings', label: '序列', kind: 'json', initial: [0.66, 1.31, 1.95, 2.6, 3.25, 3.92]},
      {name: 'shift', label: '总偏移秒', kind: 'float', initial: 0.21},
      {name: 'clock', label: '时钟来源', kind: 'select', initial: '换钟',
        options: [{value: '原时钟', label: '原时钟（照用）'}, {value: '换钟', label: '换钟（须标定）'}]},
      {name: 'metronome', label: '计拍器编号（换钟必填）', kind: 'text', initial: 'MET-NEW-01', optional: true},
      {name: 'measured_at', label: '测量时间（换钟必填）', kind: 'datetime', initial: '', optional: true},
    ],
    help: '未标定的换钟原件先收存：原拍点照录、换算留空，标定到位后用补认动作按测量时间认标定。',
    roles: ['operator', 'reviewer'],
    success: '已写入',
  },
  {
    name: 'resolve_calibration',
    label: '晚到记录补认标定',
    path: '/cue_tracks/resolve-calibration',
    fields: [
      {name: 'track', label: '换钟素材', kind: 'text', initial: 'CUE-FINAL'},
    ],
    help: '标定晚到时，按素材测量时间匹配同计拍器的生效标定并补换算。',
    roles: ['operator', 'reviewer'],
    success: '已补认',
  },
  {
    name: 'lock_track',
    label: '见证确认试投记录',
    path: '/cue_tracks/lock-track',
    fields: [
      {name: 'track', label: '试投素材', kind: 'text', initial: 'CUE-FINAL'},
    ],
    help: '换钟素材须已认用标定才可见证；见证后才进入对场可匹配集合。',
    roles: ['reviewer'],
    success: '已写入',
  },
];

const calibrationActions = [
  {
    name: 'submit_calibration',
    label: '拟合并收存时钟标定',
    path: '/clock_calibrations/submit-calibration',
    fields: [
      {name: 'code', label: '标定编号', kind: 'text', initial: 'CAL-01'},
      {name: 'metronome', label: '计拍器编号', kind: 'text', initial: 'MET-NEW-01'},
      {name: 'valid_from', label: '测量时段起', kind: 'datetime', initial: '2026-11-25T16:00'},
      {name: 'valid_to', label: '测量时段止', kind: 'datetime', initial: '2026-11-25T20:00'},
      {name: 'pairs', label: '同段新旧拍点（old/new）', kind: 'json', initial: [
        {old: 10.0, new: 10.02}, {old: 10.65, new: 10.66}, {old: 11.3, new: 11.3},
        {old: 11.95, new: 11.94}, {old: 12.6, new: 12.58}, {old: 13.25, new: 13.22},
        {old: 13.9, new: 13.86}, {old: 14.55, new: 14.5},
      ]},
    ],
    help: '末段约四分之一拍点留作检验；检验最大误差超过 0.1 秒只收存不启用，时段重叠的两份也只启用一份。',
    roles: ['operator', 'reviewer'],
    success: '已收存',
  },
];

function section(caption, columns, rows) {
  return el('section', {class: 'ledger', 'aria-label': caption},
    el('h2', {}, caption), dataView(rows, columns, 'table'));
}

export const key = 'cue_tracks';
export const title = '现场弹幕试投轨迹';

export async function render(root, role) {
  const tracks = el('div', {});
  const calibrations = el('div', {});
  const refresh = async () => {
    try {
      const [trackRows, calibrationRows] = await Promise.all([
        request('/cue_tracks'), request('/clock_calibrations')]);
      tracks.replaceChildren(section('试投节奏轨迹（原件与换算分栏留存）', TRACK_COLUMNS, trackRows));
      calibrations.replaceChildren(section('计拍器换钟标定台账', CALIBRATION_COLUMNS, calibrationRows));
    } catch (error) {
      tracks.replaceChildren(status(error.message, 'error'));
    }
  };

  const forms = [...calibrationActions, ...trackActions]
    .filter(action => action.roles.includes(role))
    .map(action => actionForm(action, refresh));

  root.replaceChildren(
    titleBlock('试投节奏轨迹', title,
      '换过计拍器后各台拍点对不上：用同段新旧拍点拟合时钟比例与偏移，留段检验，超 0.1 秒不启用。原时钟素材照用，换钟素材经标定和见证才可对场。'),
    el('div', {class: 'work stack'},
      el('div', {class: 'ledger-wrap'}, calibrations, tracks),
      el('section', {class: 'actions'}, forms)));
  await refresh();
}
